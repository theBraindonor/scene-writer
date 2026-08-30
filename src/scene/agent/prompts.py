from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROMPTS_PATH = PROJECT_ROOT / "agent-prompts.yaml"


@dataclass(frozen=True)
class PromptSet:
    coordinator_system_prompt: str
    application_agent_system_prompt: str
    continuity_editor_system_prompt: str
    rendering_fiction_prefix: str
    rendering_scene_generation_instructions: str
    rendering_requirements: tuple[str, ...]
    rendering_scene_brief_caption: str
    rendering_closing_instructions: str


def _section(raw: dict, path: Path, name: str) -> dict:
    value = raw.get(name)
    if not isinstance(value, dict):
        raise TypeError(f"{path} is malformed: expected a '{name}' mapping.")
    return value


def _field(section: dict, path: Path, section_name: str, key: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{path}: '{section_name}.{key}' is missing or empty.")
    return value


def _string_list_field(section: dict, path: Path, section_name: str, key: str) -> tuple[str, ...]:
    value = section.get(key)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise RuntimeError(f"{path}: '{section_name}.{key}' must be a non-empty list of non-empty strings.")
    return tuple(value)


def load_prompts(prompts_path: Path | None = None) -> PromptSet:
    path = prompts_path or DEFAULT_PROMPTS_PATH
    if not path.is_file():
        raise RuntimeError(f"Agent prompt config not found at {path}.")

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if not isinstance(raw, dict):
        raise TypeError(f"{path} is malformed: expected a top-level mapping.")

    coordinator = _section(raw, path, "coordinator")
    application_agent = _section(raw, path, "application_agent")
    continuity_editor = _section(raw, path, "continuity_editor")
    rendering = _section(raw, path, "rendering")

    return PromptSet(
        coordinator_system_prompt=_field(coordinator, path, "coordinator", "system_prompt"),
        application_agent_system_prompt=_field(
            application_agent, path, "application_agent", "system_prompt"
        ),
        continuity_editor_system_prompt=_field(continuity_editor, path, "continuity_editor", "system_prompt"),
        rendering_fiction_prefix=_field(rendering, path, "rendering", "fiction_prefix"),
        rendering_scene_generation_instructions=_field(
            rendering, path, "rendering", "scene_generation_instructions"
        ),
        rendering_requirements=_string_list_field(rendering, path, "rendering", "requirements"),
        rendering_scene_brief_caption=_field(rendering, path, "rendering", "scene_brief_caption"),
        rendering_closing_instructions=_field(rendering, path, "rendering", "closing_instructions"),
    )
