import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from scene.agent.registry import load_registry
from scene.agent.role import AgentRole


@dataclass(frozen=True)
class LLMConfig:
    model: str
    api_base: str | None
    api_key: str | None
    max_tokens: int | None = None
    reasoning_effort: str | None = None


def get_llm_config(role: AgentRole, registry_path: Path | None = None) -> LLMConfig:
    load_dotenv()

    profile_name = os.environ.get(role.env_var)
    if not profile_name:
        raise RuntimeError(f"{role.env_var} is not set. Set it to a profile name defined in models.yaml.")

    profiles = load_registry(registry_path)
    profile = profiles.get(profile_name)
    if profile is None:
        raise RuntimeError(f"{role.env_var}={profile_name!r} does not match any profile in models.yaml.")

    api_key = os.environ.get(profile.api_key_env) if profile.api_key_env else None
    return LLMConfig(
        model=profile.model,
        api_base=profile.api_base,
        api_key=api_key,
        max_tokens=profile.max_tokens,
        reasoning_effort=profile.reasoning_effort,
    )
