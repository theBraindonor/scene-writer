from typer.testing import CliRunner

import scene.cli.coordinator as coordinator_module
from scene.agent.config import LLMConfig
from scene.agent.role import AgentRole
from scene.cli.coordinator import app

runner = CliRunner()


def test_chat_config_resolution_failure_exits_with_clear_message(monkeypatch):
    def failing_get_llm_config(role):
        raise RuntimeError("SCENE_COORDINATING_AGENT is not set.")

    monkeypatch.setattr(coordinator_module, "get_llm_config", failing_get_llm_config)

    result = runner.invoke(app, ["chat"])

    assert result.exit_code == 1
    assert "SCENE_COORDINATING_AGENT is not set." in result.stdout
    assert result.exception is not None
    assert not isinstance(result.exception, RuntimeError)


def test_chat_launches_coordinator_app_with_resolved_config(monkeypatch):
    config = LLMConfig(model="openai/test-model", api_base=None, api_key=None)
    monkeypatch.setattr(coordinator_module, "get_llm_config", lambda role: config)

    captured = {}

    class FakeCoordinatorApp:
        def __init__(self, passed_config):
            captured["config"] = passed_config

        def run(self):
            captured["ran"] = True

    monkeypatch.setattr(coordinator_module, "CoordinatorApp", FakeCoordinatorApp)

    result = runner.invoke(app, ["chat"])

    assert result.exit_code == 0
    assert captured["config"] is config
    assert captured["ran"] is True


def test_render_config_resolution_failure_exits_with_clear_message(monkeypatch):
    def failing_get_llm_config(role):
        raise RuntimeError("SCENE_RENDERING_AGENT is not set.")

    monkeypatch.setattr(coordinator_module, "get_llm_config", failing_get_llm_config)

    result = runner.invoke(app, ["render"])

    assert result.exit_code == 1
    assert "SCENE_RENDERING_AGENT is not set." in result.stdout
    assert result.exception is not None
    assert not isinstance(result.exception, RuntimeError)


def test_render_launches_render_app_with_resolved_configs(monkeypatch):
    config = LLMConfig(model="openai/test-model", api_base=None, api_key=None)
    monkeypatch.setattr(coordinator_module, "get_llm_config", lambda role: config)

    captured = {}

    class FakeRenderApp:
        def __init__(self, passed_config, passed_continuity_config):
            captured["config"] = passed_config
            captured["continuity_config"] = passed_continuity_config

        def run(self):
            captured["ran"] = True

    monkeypatch.setattr(coordinator_module, "RenderApp", FakeRenderApp)

    result = runner.invoke(app, ["render"])

    assert result.exit_code == 0
    assert captured["config"] is config
    assert captured["continuity_config"] is config
    assert captured["ran"] is True


def test_render_continues_without_continuity_config_when_resolution_fails(monkeypatch):
    config = LLMConfig(model="openai/test-model", api_base=None, api_key=None)

    def selective_get_llm_config(role):
        if role is AgentRole.CONTINUITY_EDITING:
            raise RuntimeError("SCENE_CONTINUITY_AGENT is not set.")
        return config

    monkeypatch.setattr(coordinator_module, "get_llm_config", selective_get_llm_config)

    captured = {}

    class FakeRenderApp:
        def __init__(self, passed_config, passed_continuity_config):
            captured["config"] = passed_config
            captured["continuity_config"] = passed_continuity_config

        def run(self):
            captured["ran"] = True

    monkeypatch.setattr(coordinator_module, "RenderApp", FakeRenderApp)

    result = runner.invoke(app, ["render"])

    assert result.exit_code == 0
    assert captured["config"] is config
    assert captured["continuity_config"] is None
    assert captured["ran"] is True
    assert "Continuing without it" in result.stdout
