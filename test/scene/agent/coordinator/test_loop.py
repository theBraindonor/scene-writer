from dataclasses import dataclass, field

import scene.agent.coordinator.loop as loop_module
from scene.agent.coordinator.loop import (
    ContentDelta,
    ReasoningDelta,
    Tool,
    ToolCallFinished,
    ToolCallStarted,
    TurnComplete,
    run_turn,
)


@dataclass
class FakeFunctionDelta:
    name: str | None = None
    arguments: str | None = None


@dataclass
class FakeToolCallDelta:
    index: int
    id: str | None = None
    function: FakeFunctionDelta | None = None


@dataclass
class FakeDelta:
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[FakeToolCallDelta] | None = None


@dataclass
class FakeChoice:
    delta: FakeDelta


@dataclass
class FakeChunk:
    choices: list[FakeChoice] = field(default_factory=list)


def make_chunk(content=None, reasoning_content=None, tool_calls=None):
    return FakeChunk(choices=[FakeChoice(delta=FakeDelta(content=content, reasoning_content=reasoning_content, tool_calls=tool_calls))])


def make_scripted_stream_complete(monkeypatch, rounds):
    rounds = [list(round_chunks) for round_chunks in rounds]
    calls = []

    def fake_stream_complete(config, messages, tools=None):
        calls.append({"config": config, "messages": messages, "tools": tools})
        return iter(rounds.pop(0))

    monkeypatch.setattr(loop_module, "stream_complete", fake_stream_complete)
    return calls


@dataclass(frozen=True)
class StubConfig:
    pass


def test_plain_streamed_reply(monkeypatch):
    calls = make_scripted_stream_complete(
        monkeypatch,
        [[make_chunk(content="Hello"), make_chunk(content=" there!")]],
    )

    history = []
    events = list(run_turn(StubConfig(), history, "Hi", tools=()))

    assert events == [ContentDelta("Hello"), ContentDelta(" there!"), TurnComplete()]
    assert len(calls) == 1
    assert history == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello there!"},
    ]


def test_reasoning_deltas_interleaved_with_content(monkeypatch):
    make_scripted_stream_complete(
        monkeypatch,
        [
            [
                make_chunk(reasoning_content="Let me think..."),
                make_chunk(reasoning_content=" okay."),
                make_chunk(content="The answer is 4."),
            ]
        ],
    )

    history = []
    events = list(run_turn(StubConfig(), history, "What is 2+2?", tools=()))

    assert events == [
        ReasoningDelta("Let me think..."),
        ReasoningDelta(" okay."),
        ContentDelta("The answer is 4."),
        TurnComplete(),
    ]
    assert history[-1] == {"role": "assistant", "content": "The answer is 4."}


def test_single_tool_call_round_trip(monkeypatch):
    tool_call_delta = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="echo"))
    args_delta = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments='{"text": "hi"}'))
    calls = make_scripted_stream_complete(
        monkeypatch,
        [
            [make_chunk(tool_calls=[tool_call_delta]), make_chunk(tool_calls=[args_delta])],
            [make_chunk(content="Done")],
        ],
    )

    handled_args = []

    def handler(arguments):
        handled_args.append(arguments)
        return {"echoed": arguments["text"]}

    tools = [Tool(name="echo", schema={"type": "function", "function": {"name": "echo"}}, handler=handler)]

    history = []
    events = list(run_turn(StubConfig(), history, "please echo", tools=tools))

    assert events == [ToolCallStarted("echo"), ToolCallFinished("echo"), ContentDelta("Done"), TurnComplete()]
    assert handled_args == [{"text": "hi"}]
    assert len(calls) == 2
    assert calls[0]["tools"] == [tools[0].schema]

    assert history[0] == {"role": "user", "content": "please echo"}
    assert history[1] == {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "echo", "arguments": '{"text": "hi"}'}}],
    }
    assert history[2] == {"role": "tool", "tool_call_id": "call_1", "content": '{"echoed": "hi"}'}
    assert history[3] == {"role": "assistant", "content": "Done"}

    assert calls[1]["messages"][-1] == history[2]


def test_multiple_tool_calls_streamed_in_one_turn(monkeypatch):
    call_a_name = FakeToolCallDelta(index=0, id="call_a", function=FakeFunctionDelta(name="add_one"))
    call_b_name = FakeToolCallDelta(index=1, id="call_b", function=FakeFunctionDelta(name="add_one"))
    call_a_args = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments='{"n": 1}'))
    call_b_args = FakeToolCallDelta(index=1, function=FakeFunctionDelta(arguments='{"n": 2}'))

    make_scripted_stream_complete(
        monkeypatch,
        [
            [
                make_chunk(tool_calls=[call_a_name, call_b_name]),
                make_chunk(tool_calls=[call_a_args, call_b_args]),
            ],
            [make_chunk(content="Both done")],
        ],
    )

    def handler(arguments):
        return {"result": arguments["n"] + 1}

    tools = [Tool(name="add_one", schema={"type": "function", "function": {"name": "add_one"}}, handler=handler)]

    history = []
    events = list(run_turn(StubConfig(), history, "add ones", tools=tools))

    assert events == [
        ToolCallStarted("add_one"),
        ToolCallStarted("add_one"),
        ToolCallFinished("add_one"),
        ToolCallFinished("add_one"),
        ContentDelta("Both done"),
        TurnComplete(),
    ]
    tool_results = [entry for entry in history if entry["role"] == "tool"]
    assert tool_results == [
        {"role": "tool", "tool_call_id": "call_a", "content": '{"result": 2}'},
        {"role": "tool", "tool_call_id": "call_b", "content": '{"result": 3}'},
    ]


def test_unknown_tool_reports_error_without_raising(monkeypatch):
    tool_call_delta = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="does-not-exist"))
    make_scripted_stream_complete(
        monkeypatch,
        [
            [make_chunk(tool_calls=[tool_call_delta])],
            [make_chunk(content="Sorted")],
        ],
    )

    history = []
    events = list(run_turn(StubConfig(), history, "do the thing", tools=()))

    assert events[-1] == TurnComplete()
    assert ContentDelta("Sorted") in events
    tool_result = next(entry for entry in history if entry["role"] == "tool")
    assert tool_result["tool_call_id"] == "call_1"
    assert "does-not-exist" in tool_result["content"]


def test_empty_tool_registry_sends_no_tools_kwarg(monkeypatch):
    calls = make_scripted_stream_complete(monkeypatch, [[make_chunk(content="hi")]])

    list(run_turn(StubConfig(), [], "hello", tools=()))

    assert calls[0]["tools"] is None
