import scene.agent.llm as llm_module
from scene.agent.config import LLMConfig
from scene.agent.llm import complete, stream_complete


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


def test_complete_includes_api_key_without_api_base(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return "response"

    monkeypatch.setattr(llm_module.litellm, "completion", fake_completion)

    config = LLMConfig(model="openrouter/anthropic/claude-3.5-sonnet", api_base=None, api_key="sk-or-test")
    messages = [{"role": "user", "content": "hello"}]

    complete(config, messages)

    assert captured == {
        "model": "openrouter/anthropic/claude-3.5-sonnet",
        "messages": messages,
        "api_key": "sk-or-test",
    }


def test_complete_defaults_api_key_when_api_base_set_without_key(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return "response"

    monkeypatch.setattr(llm_module.litellm, "completion", fake_completion)

    config = LLMConfig(model="openai/my-model", api_base="http://localhost:1234/v1", api_key=None)
    messages = [{"role": "user", "content": "hello"}]

    complete(config, messages)

    assert captured["api_base"] == "http://localhost:1234/v1"
    assert captured["api_key"] == "not-needed"


def test_complete_includes_max_tokens_and_reasoning_effort(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return "response"

    monkeypatch.setattr(llm_module.litellm, "completion", fake_completion)

    config = LLMConfig(
        model="openrouter/aion-labs/aion-3.0-mini",
        api_base=None,
        api_key="sk-test",
        max_tokens=4096,
        reasoning_effort="low",
    )
    messages = [{"role": "user", "content": "hello"}]

    complete(config, messages)

    assert captured["max_tokens"] == 4096
    assert captured["reasoning_effort"] == "low"


def test_stream_complete_passes_stream_true(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return iter(["chunk"])

    monkeypatch.setattr(llm_module.litellm, "completion", fake_completion)

    config = LLMConfig(model="openai/my-model", api_base=None, api_key=None)
    messages = [{"role": "user", "content": "hello"}]

    result = stream_complete(config, messages)

    assert list(result) == ["chunk"]
    assert captured == {"model": "openai/my-model", "messages": messages, "stream": True}


def test_stream_complete_includes_api_base_api_key_and_tools(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return iter([])

    monkeypatch.setattr(llm_module.litellm, "completion", fake_completion)

    config = LLMConfig(model="openai/my-model", api_base="http://localhost:1234/v1", api_key="sk-test")
    messages = [{"role": "user", "content": "hello"}]
    tools = [{"type": "function", "function": {"name": "noop"}}]

    stream_complete(config, messages, tools=tools)

    assert captured == {
        "model": "openai/my-model",
        "messages": messages,
        "api_base": "http://localhost:1234/v1",
        "api_key": "sk-test",
        "tools": tools,
        "stream": True,
    }
