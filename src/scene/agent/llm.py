from typing import Any

import litellm

from scene.agent.config import LLMConfig


def complete(config: LLMConfig, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> Any:
    kwargs: dict[str, Any] = {"model": config.model, "messages": messages}
    if config.api_base is not None:
        kwargs["api_base"] = config.api_base
    if config.api_key is not None:
        kwargs["api_key"] = config.api_key
    if tools is not None:
        kwargs["tools"] = tools

    return litellm.completion(**kwargs)
