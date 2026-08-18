from dataclasses import dataclass, field

import scene.agent.coordinator.loop as loop_module
from scene.agent.coordinator.loop import Tool, run_turn


@dataclass
class FakeFunctionCall:
    name: str
    arguments: str


@dataclass
class FakeToolCall:
    id: str
    function: FakeFunctionCall


@dataclass
class FakeMessage:
    content: str | None
    tool_calls: list[FakeToolCall] | None = None


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeResponse:
    choices: list[FakeChoice] = field(default_factory=list)


def make_response(content=None, tool_calls=None):
    return FakeResponse(choices=[FakeChoice(message=FakeMessage(content=content, tool_calls=tool_calls))])


def make_scripted_complete(monkeypatch, responses):
    responses = list(responses)
    calls = []

    def fake_complete(config, messages, tools=None):
        calls.append({"config": config, "messages": messages, "tools": tools})
        return responses.pop(0)

    monkeypatch.setattr(loop_module, "complete", fake_complete)
    return calls


@dataclass(frozen=True)
class StubConfig:
    pass


def test_plain_turn_with_no_tool_calls(monkeypatch):
    calls = make_scripted_complete(monkeypatch, [make_response(content="Hello there!")])

    history = []
    reply = run_turn(StubConfig(), history, "Hi", tools=())

    assert reply == "Hello there!"
    assert len(calls) == 1
    assert history == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello there!"},
    ]


def test_single_tool_call_round_trip(monkeypatch):
    tool_call = FakeToolCall(id="call_1", function=FakeFunctionCall(name="echo", arguments='{"text": "hi"}'))
    calls = make_scripted_complete(
        monkeypatch,
        [
            make_response(content=None, tool_calls=[tool_call]),
            make_response(content="Done"),
        ],
    )

    handled_args = []

    def handler(arguments):
        handled_args.append(arguments)
        return {"echoed": arguments["text"]}

    tools = [Tool(name="echo", schema={"type": "function", "function": {"name": "echo"}}, handler=handler)]

    history = []
    reply = run_turn(StubConfig(), history, "please echo", tools=tools)

    assert reply == "Done"
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

    # The second complete() call must include the tool result in the outgoing messages.
    assert calls[1]["messages"][-1] == history[2]


def test_multiple_sequential_tool_calls_in_one_turn(monkeypatch):
    tool_call_a = FakeToolCall(id="call_a", function=FakeFunctionCall(name="add_one", arguments='{"n": 1}'))
    tool_call_b = FakeToolCall(id="call_b", function=FakeFunctionCall(name="add_one", arguments='{"n": 2}'))
    make_scripted_complete(
        monkeypatch,
        [
            make_response(content=None, tool_calls=[tool_call_a, tool_call_b]),
            make_response(content="Both done"),
        ],
    )

    def handler(arguments):
        return {"result": arguments["n"] + 1}

    tools = [Tool(name="add_one", schema={"type": "function", "function": {"name": "add_one"}}, handler=handler)]

    history = []
    reply = run_turn(StubConfig(), history, "add ones", tools=tools)

    assert reply == "Both done"
    tool_results = [entry for entry in history if entry["role"] == "tool"]
    assert tool_results == [
        {"role": "tool", "tool_call_id": "call_a", "content": '{"result": 2}'},
        {"role": "tool", "tool_call_id": "call_b", "content": '{"result": 3}'},
    ]


def test_unknown_tool_reports_error_without_raising(monkeypatch):
    tool_call = FakeToolCall(id="call_1", function=FakeFunctionCall(name="does-not-exist", arguments="{}"))
    make_scripted_complete(
        monkeypatch,
        [
            make_response(content=None, tool_calls=[tool_call]),
            make_response(content="Sorted"),
        ],
    )

    history = []
    reply = run_turn(StubConfig(), history, "do the thing", tools=())

    assert reply == "Sorted"
    tool_result = next(entry for entry in history if entry["role"] == "tool")
    assert tool_result["tool_call_id"] == "call_1"
    assert "does-not-exist" in tool_result["content"]


def test_empty_tool_registry_sends_no_tools_kwarg(monkeypatch):
    calls = make_scripted_complete(monkeypatch, [make_response(content="hi")])

    run_turn(StubConfig(), [], "hello", tools=())

    assert calls[0]["tools"] is None
