from typing import Any

import litellm

from scene.agent.config import LLMConfig


def _build_kwargs(
    config: LLMConfig, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"model": config.model, "messages": messages}
    if config.api_base is not None:
        kwargs["api_base"] = config.api_base
        # Local OpenAI-compatible servers (e.g. LM Studio) don't validate the key, but
        # litellm's underlying OpenAI client still requires a non-empty string to be set.
        kwargs["api_key"] = config.api_key or "not-needed"
    elif config.api_key is not None:
        kwargs["api_key"] = config.api_key
    if tools is not None:
        kwargs["tools"] = tools
    return kwargs


def complete(config: LLMConfig, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> Any:
    return litellm.completion(**_build_kwargs(config, messages, tools))


def stream_complete(config: LLMConfig, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> Any:
    return litellm.completion(**_build_kwargs(config, messages, tools), stream=True)
