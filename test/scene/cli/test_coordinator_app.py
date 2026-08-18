from dataclasses import dataclass, field

import pytest
from textual.widgets import Input, Static

import scene.agent.coordinator.loop as loop_module
import scene.data.database as database_module
from scene.agent.config import LLMConfig
from scene.cli.coordinator_app import CoordinatorApp


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


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


def make_response(content):
    return FakeResponse(choices=[FakeChoice(message=FakeMessage(content=content))])


def make_config():
    return LLMConfig(model="openai/test-model", api_base=None, api_key=None)


async def send(pilot, text):
    pilot.app.query_one("#chat-input", Input).value = text
    await pilot.press("enter")
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def test_quit_command_exits_app():
    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "/quit")
        assert not app.is_running


async def test_unknown_slash_command_shows_notice():
    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "/bogus")
        assert app.chat_lines == ["Unknown command: /bogus"]


async def test_plain_chat_turn_appends_reply(monkeypatch):
    responses = [make_response("Hello there!")]
    monkeypatch.setattr(loop_module, "complete", lambda config, messages, tools=None: responses.pop(0))

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "hi")

        assert "You: hi" in app.chat_lines
        assert "Coordinator: Hello there!" in app.chat_lines
        assert app.state.history[-1] == {"role": "assistant", "content": "Hello there!"}


async def test_story_pane_shows_placeholder_until_a_story_exists():
    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        assert "No current story" in pilot.app.query_one("#story-pane", Static).content


async def test_tool_call_creates_story_and_updates_story_pane(monkeypatch):
    tool_call = FakeToolCall(
        id="call_1",
        function=FakeFunctionCall(name="create_story", arguments='{"title": "New Story", "scenario": "A scenario"}'),
    )
    responses = [
        make_response(content=None),
        make_response(content="Created it!"),
    ]
    responses[0].choices[0].message.tool_calls = [tool_call]
    monkeypatch.setattr(loop_module, "complete", lambda config, messages, tools=None: responses.pop(0))

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "please create a story")

        assert app.state.current_story_id is not None
        pane_text = pilot.app.query_one("#story-pane", Static).content
        assert "New Story" in pane_text
        assert "A scenario" in pane_text


async def test_blank_input_is_ignored():
    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "   ")
        assert app.chat_lines == []


async def test_input_submitted_from_other_widget_is_ignored():
    app = CoordinatorApp(make_config())

    class FakeInput:
        id = "not-chat-input"

    class FakeSubmitted:
        input = FakeInput()
        value = "hello"

    async with app.run_test():
        app.on_input_submitted(FakeSubmitted())
        assert app.chat_lines == []


def test_render_story_pane_handles_missing_story():
    app = CoordinatorApp(make_config())
    app.state.current_story_id = 999

    assert "999" in app._render_story_pane()
    assert "not found" in app._render_story_pane()


async def test_clear_resets_history_current_story_and_panes(monkeypatch):
    tool_call = FakeToolCall(
        id="call_1",
        function=FakeFunctionCall(name="create_story", arguments='{"title": "New Story", "scenario": "A scenario"}'),
    )
    responses = [make_response(content=None), make_response(content="Created it!")]
    responses[0].choices[0].message.tool_calls = [tool_call]
    monkeypatch.setattr(loop_module, "complete", lambda config, messages, tools=None: responses.pop(0))

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "please create a story")
        assert app.state.current_story_id is not None

        await send(pilot, "/clear")

        assert app.state.current_story_id is None
        assert app.state.history == []
        assert app.chat_lines == []
        assert "No current story" in pilot.app.query_one("#story-pane", Static).content
