from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from scene.agent.config import LLMConfig
from scene.agent.llm import stream_complete
from scene.agent.prompts import load_prompts
from scene.core.character import get_character
from scene.core.continuity_snapshot import get_preceding_snapshot
from scene.core.rendering import list_renderings
from scene.core.scene import list_scenes
from scene.core.scene_character import list_characters_for_scene
from scene.core.scene_location import list_locations_for_scene
from scene.core.story import get_story
from scene.data.character import Character
from scene.data.location import Location
from scene.data.scene import Scene


def find_next_unrendered_scene(session: Session, story_id: int) -> Scene | None:
    for scene in list_scenes(session, story_id):
        renderings = list_renderings(session, scene.id)
        if not any(rendering.is_active for rendering in renderings):
            return scene
    return None


def earlier_scenes_rendered(session: Session, story_id: int, target_position: int) -> bool:
    for scene in list_scenes(session, story_id):
        if scene.position >= target_position:
            continue
        if not any(rendering.is_active for rendering in list_renderings(session, scene.id)):
            return False
    return True


def _headed(heading: str, body: str) -> str:
    return f"## {heading}\n\n{body}"


def _requirements_section(requirements: tuple[str, ...]) -> str:
    bullet_lines = "\n".join(f"- {item}" for item in requirements)
    return _headed("Requirements", bullet_lines)


def _scene_brief_fields_text(session: Session, scene: Scene) -> str:
    lines: list[str] = []
    if scene.heading:
        lines.append(f"Heading: {scene.heading}")
    if scene.pov_character_id is not None:
        pov_character = get_character(session, scene.pov_character_id)
        if pov_character is not None:
            lines.append(f"Point of view: {pov_character.name}")
    lines.append(f"Brief: {scene.brief}")
    if scene.required_actions:
        lines.append(f"Required actions: {scene.required_actions}")
    if scene.desired_outcome:
        lines.append(f"Desired outcome: {scene.desired_outcome}")
    if scene.target_length:
        lines.append(f"Target length: {scene.target_length}")
    return "\n".join(lines)


def _character_card(character: Character) -> str:
    lines = [f"CHARACTER: {character.name}"]
    if character.description:
        lines.append(f"Enduring details: {character.description}")
    if character.motive:
        lines.append(f"Core motive: {character.motive}")
    return "\n".join(lines)


def _location_card(location: Location) -> str:
    lines = [f"LOCATION: {location.name}"]
    if location.description:
        lines.append(location.description)
    return "\n".join(lines)


def _active_rendering_body_or_none(session: Session, scene: Scene) -> str | None:
    active = next((rendering for rendering in list_renderings(session, scene.id) if rendering.is_active), None)
    return active.body if active is not None else None


def build_render_messages(session: Session, story_id: int, target_scene_id: int) -> list[dict[str, Any]]:
    story = get_story(session, story_id)
    if story is None:
        raise ValueError(f"Story {story_id} not found.")

    scenes = list_scenes(session, story_id)
    target = next((scene for scene in scenes if scene.id == target_scene_id), None)
    if target is None:
        raise ValueError(f"Scene {target_scene_id} not found in story {story_id}.")

    prompts = load_prompts()
    system_lines = [
        prompts.rendering_fiction_prefix,
        _requirements_section(prompts.rendering_requirements),
        _headed("Story Brief", story.story_brief),
    ]
    if story.style_guidance:
        system_lines.append(_headed("Style Guidance", story.style_guidance))
    if story.generation_guideance:
        system_lines.append(_headed("Generation Guidance", story.generation_guideance))

    characters = list_characters_for_scene(session, target.id)
    if characters:
        system_lines.append(_headed("Cast of Characters", "\n\n".join(_character_card(c) for c in characters)))

    locations = list_locations_for_scene(session, target.id)
    if locations:
        system_lines.append(_headed("Locations", "\n\n".join(_location_card(loc) for loc in locations)))

    system_lines.append(_headed("Scene Generation Instructions", prompts.rendering_scene_generation_instructions))
    messages: list[dict[str, Any]] = [{"role": "system", "content": "\n\n".join(system_lines)}]

    target_index = scenes.index(target)
    preceding_scene = scenes[target_index - 1] if target_index > 0 else None

    user_sections = []
    if preceding_scene is not None:
        preceding_snapshot = get_preceding_snapshot(session, story_id, target.id)
        if preceding_snapshot is not None:
            user_sections.append(_headed("Current Canon", preceding_snapshot.narrative_state))

        recent_prose = _active_rendering_body_or_none(session, preceding_scene)
        if recent_prose is not None:
            user_sections.append(_headed("Optional Recent Prose", recent_prose))

    scene_brief_body = f"{prompts.rendering_scene_brief_caption}\n\n{_scene_brief_fields_text(session, target)}"
    user_sections.append(_headed("Scene Brief", scene_brief_body))
    user_sections.append(_headed("Final Instructions", prompts.rendering_closing_instructions))
    messages.append({"role": "user", "content": "\n\n".join(user_sections)})
    return messages


@dataclass(frozen=True)
class RenderReasoningDelta:
    text: str


@dataclass(frozen=True)
class RenderContentDelta:
    text: str


@dataclass(frozen=True)
class RenderComplete:
    text: str
    reasoning: str = ""


RenderEvent = RenderReasoningDelta | RenderContentDelta | RenderComplete


def stream_render(config: LLMConfig, messages: list[dict[str, Any]]) -> Iterator[RenderEvent]:
    content_parts: list[str] = []
    reasoning_parts: list[str] = []

    for chunk in stream_complete(config, messages):
        delta = chunk.choices[0].delta

        reasoning_piece = getattr(delta, "reasoning_content", None)
        if reasoning_piece:
            reasoning_parts.append(reasoning_piece)
            yield RenderReasoningDelta(reasoning_piece)

        content_piece = getattr(delta, "content", None)
        if content_piece:
            content_parts.append(content_piece)
            yield RenderContentDelta(content_piece)

    yield RenderComplete(text="".join(content_parts), reasoning="".join(reasoning_parts))
