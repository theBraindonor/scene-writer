from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from scene.agent.config import LLMConfig
from scene.agent.llm import stream_complete
from scene.core.rendering import list_renderings
from scene.core.scene import list_scenes
from scene.core.scene_character import list_characters_for_scene
from scene.core.scene_location import list_locations_for_scene
from scene.core.story import get_story
from scene.data.scene import Scene


def find_next_unrendered_scene(session: Session, story_id: int) -> Scene | None:
    for scene in list_scenes(session, story_id):
        renderings = list_renderings(session, scene.id)
        if not any(rendering.is_active for rendering in renderings):
            return scene
    return None


def _scene_detail_text(session: Session, scene: Scene) -> str:
    lines = [
        f"Scene {scene.position}: {scene.heading or '(untitled)'}",
        f"Description: {scene.description}",
        f"Required actions: {scene.required_actions or '(none)'}",
        f"Length: {scene.length or '(unspecified)'}",
    ]

    characters = list_characters_for_scene(session, scene.id)
    lines.append("Characters:")
    if characters:
        for character in characters:
            lines.append(
                f"- {character.name}: {character.description or '(no description)'} "
                f"(Motive: {character.motive or '(none)'})"
            )
    else:
        lines.append("(none)")

    locations = list_locations_for_scene(session, scene.id)
    lines.append("Locations:")
    if locations:
        for location in locations:
            lines.append(f"- {location.name}: {location.description or '(no description)'}")
    else:
        lines.append("(none)")

    return "\n".join(lines)


def _active_rendering_body(session: Session, scene: Scene) -> str:
    active = next((rendering for rendering in list_renderings(session, scene.id) if rendering.is_active), None)
    if active is None:
        raise ValueError(f"Scene {scene.id} has no active rendering.")
    return active.body


def build_render_messages(session: Session, story_id: int, target_scene_id: int) -> list[dict[str, Any]]:
    story = get_story(session, story_id)
    if story is None:
        raise ValueError(f"Story {story_id} not found.")

    scenes = list_scenes(session, story_id)
    target = next((scene for scene in scenes if scene.id == target_scene_id), None)
    if target is None:
        raise ValueError(f"Scene {target_scene_id} not found in story {story_id}.")

    system_lines = [f"Scenario:\n{story.scenario}"]
    if story.style_guidance:
        system_lines.append(f"Style guidance:\n{story.style_guidance}")
    system_lines.append(
        "You are writing one scene at a time for this story. Write only the requested "
        "scene's prose; do not summarize, repeat, or continue past it."
    )
    messages: list[dict[str, Any]] = [{"role": "system", "content": "\n\n".join(system_lines)}]

    for scene in scenes:
        if scene.position >= target.position:
            continue
        messages.append({"role": "user", "content": _scene_detail_text(session, scene)})
        messages.append({"role": "assistant", "content": _active_rendering_body(session, scene)})

    target_prompt = f"{_scene_detail_text(session, target)}\n\nWrite this scene's prose now."
    messages.append({"role": "user", "content": target_prompt})
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


RenderEvent = RenderReasoningDelta | RenderContentDelta | RenderComplete


def stream_render(config: LLMConfig, messages: list[dict[str, Any]]) -> Iterator[RenderEvent]:
    content_parts: list[str] = []

    for chunk in stream_complete(config, messages):
        delta = chunk.choices[0].delta

        reasoning_piece = getattr(delta, "reasoning_content", None)
        if reasoning_piece:
            yield RenderReasoningDelta(reasoning_piece)

        content_piece = getattr(delta, "content", None)
        if content_piece:
            content_parts.append(content_piece)
            yield RenderContentDelta(content_piece)

    yield RenderComplete("".join(content_parts))
