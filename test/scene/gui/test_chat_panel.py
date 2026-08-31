from dataclasses import dataclass, field

import pytest

import scene.agent.coordinator.loop as loop_module
import scene.data.database as database_module
from scene.agent.application.state import ApplicationState
from scene.agent.application.tools.story import build_story_tools
from scene.agent.config import LLMConfig
from scene.gui.chat_panel import ChatPanel, _AgentTurnWidget, _UserMessageWidget

TEST_SYSTEM_PROMPT = "Test system prompt."


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


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
    return FakeChunk(
        choices=[
            FakeChoice(delta=FakeDelta(content=content, reasoning_content=reasoning_content, tool_calls=tool_calls))
        ]
    )


def script_stream(monkeypatch, rounds):
    rounds = [list(round_chunks) for round_chunks in rounds]

    def fake_stream_complete(config, messages, tools=None):
        return iter(rounds.pop(0))

    monkeypatch.setattr(loop_module, "stream_complete", fake_stream_complete)


def make_config():
    return LLMConfig(model="openai/test-model", api_base=None, api_key=None)


def make_panel(qtbot, error=None, system_prompt=TEST_SYSTEM_PROMPT):
    state = ApplicationState()
    tools = build_story_tools(state)
    panel = ChatPanel(make_config(), state, tools, system_prompt=system_prompt, error=error)
    qtbot.addWidget(panel)
    panel.show()
    return panel, state


def send(qtbot, panel, text):
    panel.input_edit.setText(text)
    with qtbot.waitSignal(panel.turn_completed, timeout=2000):
        panel.input_edit.returnPressed.emit()


def transcript_widgets(panel, widget_type):
    return [
        panel.transcript_layout.itemAt(i).widget()
        for i in range(panel.transcript_layout.count())
        if isinstance(panel.transcript_layout.itemAt(i).widget(), widget_type)
    ]


def test_sending_message_streams_scripted_response(qtbot, monkeypatch):
    script_stream(monkeypatch, [[make_chunk(content="Hello"), make_chunk(content=" there!")]])
    panel, _state = make_panel(qtbot)

    send(qtbot, panel, "hi")

    user_messages = transcript_widgets(panel, _UserMessageWidget)
    assert len(user_messages) == 1

    agent_blocks = transcript_widgets(panel, _AgentTurnWidget)
    assert len(agent_blocks) == 1
    assert agent_blocks[0].answer_label.text() == "Hello there!"
    assert panel.input_edit.isEnabled()
    assert panel.input_edit.text() == ""


def test_reasoning_and_tool_calls_are_shown(qtbot, monkeypatch):
    tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_story"))
    args = FakeToolCallDelta(
        index=0, function=FakeFunctionDelta(arguments='{"title": "New Story", "story_brief": "A scenario"}')
    )
    script_stream(
        monkeypatch,
        [
            [make_chunk(reasoning_content="Thinking..."), make_chunk(tool_calls=[tool_call]), make_chunk(tool_calls=[args])],
            [make_chunk(content="Created it!")],
        ],
    )
    panel, state = make_panel(qtbot)

    send(qtbot, panel, "please create a story")

    block = transcript_widgets(panel, _AgentTurnWidget)[0]
    assert block.reasoning_label.text() == "Thinking..."
    assert "create_story" in block.tool_calls_label.text()
    assert state.current_story_id is not None


def test_tool_call_finished_emitted_once_per_tool_call_before_turn_completed(qtbot, monkeypatch):
    open_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="open_story"))
    open_args = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments="{}"))
    select_call = FakeToolCallDelta(index=1, id="call_2", function=FakeFunctionDelta(name="unarchive_story"))
    select_args = FakeToolCallDelta(index=1, function=FakeFunctionDelta(arguments="{}"))
    script_stream(
        monkeypatch,
        [
            [
                make_chunk(tool_calls=[open_call]),
                make_chunk(tool_calls=[open_args]),
                make_chunk(tool_calls=[select_call]),
                make_chunk(tool_calls=[select_args]),
            ],
            [make_chunk(content="Done!")],
        ],
    )
    panel, _state = make_panel(qtbot)

    finished_count = []
    panel.tool_call_finished.connect(lambda: finished_count.append(len(finished_count)))
    turn_completed_seen_at = []
    panel.turn_completed.connect(lambda: turn_completed_seen_at.append(len(finished_count)))

    send(qtbot, panel, "please open and unarchive")

    # Both tool calls fired tool_call_finished, and both had already fired by the time
    # turn_completed arrived -- proving the per-tool-call signal isn't just a duplicate of
    # the end-of-turn one, but genuinely precedes it.
    assert len(finished_count) == 2
    assert turn_completed_seen_at == [2]


def test_blank_input_is_ignored(qtbot, monkeypatch):
    def unexpected_stream_complete(config, messages, tools=None):
        raise AssertionError("stream_complete() should not be called for blank input")

    monkeypatch.setattr(loop_module, "stream_complete", unexpected_stream_complete)
    panel, _state = make_panel(qtbot)

    panel.input_edit.setText("   ")
    panel.input_edit.returnPressed.emit()

    assert transcript_widgets(panel, _UserMessageWidget) == []


def test_error_config_disables_input(qtbot):
    panel, _state = make_panel(qtbot, error="Could not resolve the application agent's model: boom")

    assert not panel.input_edit.isEnabled()
    assert panel.status_label.isVisible()
    assert "boom" in panel.status_label.text()


def test_uses_provided_system_prompt(qtbot, monkeypatch):
    captured_messages = []

    def fake_stream_complete(config, messages, tools=None):
        captured_messages.append(messages)
        return iter([make_chunk(content="Hello!")])

    monkeypatch.setattr(loop_module, "stream_complete", fake_stream_complete)
    panel, _state = make_panel(qtbot, system_prompt="Custom prompt for this agent.")

    send(qtbot, panel, "hi")

    assert captured_messages[0][0] == {"role": "system", "content": "Custom prompt for this agent."}


def test_transcript_has_white_background(qtbot):
    panel, _state = make_panel(qtbot)

    style = panel.transcript_container.styleSheet().lower()
    assert "background-color: white" in style


def test_toggle_button_collapses_and_expands_content_and_clear_button(qtbot):
    panel, _state = make_panel(qtbot)

    assert panel.content_widget.isVisible()
    assert panel.clear_button.isVisible()
    assert panel.toggle_button.text() == ChatPanel.EXPANDED_LABEL

    panel.toggle_button.click()
    assert not panel.content_widget.isVisible()
    assert not panel.clear_button.isVisible()
    assert panel.toggle_button.text() == ChatPanel.COLLAPSED_LABEL

    panel.toggle_button.click()
    assert panel.content_widget.isVisible()
    assert panel.clear_button.isVisible()
    assert panel.toggle_button.text() == ChatPanel.EXPANDED_LABEL


def test_toggle_button_emits_collapse_toggled(qtbot):
    panel, _state = make_panel(qtbot)

    with qtbot.waitSignal(panel.collapse_toggled, timeout=1000) as blocker:
        panel.toggle_button.click()
    assert blocker.args == [False]

    with qtbot.waitSignal(panel.collapse_toggled, timeout=1000) as blocker:
        panel.toggle_button.click()
    assert blocker.args == [True]


def test_clear_button_empties_transcript_and_history(qtbot, monkeypatch):
    script_stream(monkeypatch, [[make_chunk(content="Hello there!")]])
    panel, state = make_panel(qtbot)
    send(qtbot, panel, "hi")
    assert transcript_widgets(panel, _UserMessageWidget)
    assert state.history

    panel.clear_button.click()

    assert transcript_widgets(panel, _UserMessageWidget) == []
    assert transcript_widgets(panel, _AgentTurnWidget) == []
    assert state.history == []


def test_clear_button_does_nothing_while_turn_in_flight(qtbot, monkeypatch):
    gate_events = []

    def blocking_stream_complete(config, messages, tools=None):
        gate_events.append(1)
        return iter([make_chunk(content="Hello!")])

    monkeypatch.setattr(loop_module, "stream_complete", blocking_stream_complete)
    panel, state = make_panel(qtbot)
    state.history.append({"role": "user", "content": "existing message"})

    panel.input_edit.setEnabled(False)
    panel.clear_button.click()

    assert state.history == [{"role": "user", "content": "existing message"}]


def test_transcript_scrolls_to_bottom_as_messages_are_added(qtbot, monkeypatch):
    script_stream(monkeypatch, [[make_chunk(content=f"Reply {i}.")] for i in range(8)])
    panel, _state = make_panel(qtbot)
    panel.resize(300, 150)

    for i in range(8):
        send(qtbot, panel, f"message {i}")

    scroll_bar = panel.transcript_scroll.verticalScrollBar()
    assert scroll_bar.maximum() > 0
    assert scroll_bar.value() == scroll_bar.maximum()
