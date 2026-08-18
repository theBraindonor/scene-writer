import scene.agent.llm as llm_module
from scene.agent.config import LLMConfig
from scene.agent.llm import complete


def test_complete_passes_model_and_messages(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return "response"

    monkeypatch.setattr(llm_module.litellm, "completion", fake_completion)

    config = LLMConfig(model="openai/my-model", api_base=None, api_key=None)
    messages = [{"role": "user", "content": "hello"}]

    result = complete(config, messages)

    assert result == "response"
    assert captured == {"model": "openai/my-model", "messages": messages}


def test_complete_includes_api_base_api_key_and_tools(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return "response"

    monkeypatch.setattr(llm_module.litellm, "completion", fake_completion)

    config = LLMConfig(model="openai/my-model", api_base="http://localhost:1234/v1", api_key="sk-test")
    messages = [{"role": "user", "content": "hello"}]
    tools = [{"type": "function", "function": {"name": "noop"}}]

    complete(config, messages, tools=tools)

    assert captured == {
        "model": "openai/my-model",
        "messages": messages,
        "api_base": "http://localhost:1234/v1",
        "api_key": "sk-test",
        "tools": tools,
    }
