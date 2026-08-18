from dataclasses import dataclass, field

import pytest
from typer.testing import CliRunner

import scene.agent.coordinator.loop as loop_module
import scene.cli.coordinator as coordinator_module
import scene.data.database as database_module
from scene.agent.config import LLMConfig
from scene.cli.coordinator import app
from scene.core.story import create_story, get_story
from scene.data.database import session_scope

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


@pytest.fixture
def story_id():
    with session_scope() as session:
        story = create_story(session, title="My Story", scenario="A scenario")
        return story.id


@pytest.fixture(autouse=True)
def stub_llm_config(monkeypatch):
    monkeypatch.setattr(
        coordinator_module, "get_llm_config", lambda role: LLMConfig(model="openai/test-model", api_base=None, api_key=None)
    )


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


def test_chat_with_missing_story_exits_with_message():
    result = runner.invoke(app, ["chat", "999"])

    assert result.exit_code == 1
    assert "Story 999 not found" in result.stdout


def test_chat_prints_assistant_reply_and_exits_cleanly(monkeypatch, story_id):
    responses = [make_response("Hello! How can I help with your story?")]
    monkeypatch.setattr(loop_module, "complete", lambda config, messages, tools=None: responses.pop(0))

    result = runner.invoke(app, ["chat", str(story_id)], input="hi there\nexit\n")

    assert result.exit_code == 0
    assert "Hello! How can I help with your story?" in result.stdout


def test_chat_exit_command_ends_repl_without_calling_llm(monkeypatch, story_id):
    def unexpected_complete(config, messages, tools=None):
        raise AssertionError("complete() should not be called when the first input is 'exit'")

    monkeypatch.setattr(loop_module, "complete", unexpected_complete)

    result = runner.invoke(app, ["chat", str(story_id)], input="exit\n")

    assert result.exit_code == 0


def test_chat_eof_ends_repl_cleanly(monkeypatch, story_id):
    def unexpected_complete(config, messages, tools=None):
        raise AssertionError("complete() should not be called when stdin hits EOF immediately")

    monkeypatch.setattr(loop_module, "complete", unexpected_complete)

    result = runner.invoke(app, ["chat", str(story_id)], input="")

    assert result.exit_code == 0


def test_chat_tool_call_updates_story_and_persists(monkeypatch, story_id):
    tool_call = FakeToolCall(
        id="call_1",
        function=FakeFunctionCall(name="update_story", arguments='{"scenario": "A brand new scenario"}'),
    )
    responses = [
        make_response(content=None),
        make_response(content="Updated the scenario for you."),
    ]
    responses[0].choices[0].message.tool_calls = [tool_call]
    monkeypatch.setattr(loop_module, "complete", lambda config, messages, tools=None: responses.pop(0))

    result = runner.invoke(app, ["chat", str(story_id)], input="update the scenario please\nexit\n")

    assert result.exit_code == 0
    assert "Updated the scenario for you." in result.stdout

    with session_scope() as session:
        story = get_story(session, story_id)
        assert story.scenario == "A brand new scenario"


def test_chat_config_resolution_failure_exits_with_clear_message(monkeypatch, story_id):
    def failing_get_llm_config(role):
        raise RuntimeError("SCENE_COORDINATING_AGENT is not set.")

    monkeypatch.setattr(coordinator_module, "get_llm_config", failing_get_llm_config)

    result = runner.invoke(app, ["chat", str(story_id)])

    assert result.exit_code == 1
    assert "SCENE_COORDINATING_AGENT is not set." in result.stdout
    assert result.exception is not None
    assert not isinstance(result.exception, RuntimeError)
