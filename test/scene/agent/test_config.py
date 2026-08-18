import pytest

import scene.agent.config as config_module
from scene.agent.config import LLMConfig, get_llm_config
from scene.agent.role import AgentRole


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)


@pytest.fixture
def registry_path(tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text(
        """
        profiles:
          openrouter-instruct:
            model: openrouter/anthropic/claude-3.5-sonnet
            api_key_env: OPENROUTER_API_KEY
          lmstudio-instruct:
            model: openai/my-model
            api_base: http://localhost:1234/v1
        """,
        encoding="utf-8",
    )
    return path


def test_resolves_profile_with_api_key(monkeypatch, registry_path):
    monkeypatch.setenv("SCENE_COORDINATING_AGENT", "openrouter-instruct")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    result = get_llm_config(AgentRole.COORDINATING, registry_path=registry_path)

    assert result == LLMConfig(model="openrouter/anthropic/claude-3.5-sonnet", api_base=None, api_key="sk-test")


def test_resolves_profile_without_api_key_env(monkeypatch, registry_path):
    monkeypatch.setenv("SCENE_COORDINATING_AGENT", "lmstudio-instruct")

    result = get_llm_config(AgentRole.COORDINATING, registry_path=registry_path)

    assert result == LLMConfig(model="openai/my-model", api_base="http://localhost:1234/v1", api_key=None)


def test_missing_role_env_var_raises(monkeypatch, registry_path):
    monkeypatch.delenv("SCENE_COORDINATING_AGENT", raising=False)

    with pytest.raises(RuntimeError, match="SCENE_COORDINATING_AGENT"):
        get_llm_config(AgentRole.COORDINATING, registry_path=registry_path)


def test_unknown_profile_raises(monkeypatch, registry_path):
    monkeypatch.setenv("SCENE_COORDINATING_AGENT", "does-not-exist")

    with pytest.raises(RuntimeError, match="does-not-exist"):
        get_llm_config(AgentRole.COORDINATING, registry_path=registry_path)
