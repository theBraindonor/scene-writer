from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from scene.agent.config import LLMConfig
from scene.agent.llm import stream_complete
from scene.core.character import get_character, list_characters
from scene.core.location import list_locations
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
    character_names = ", ".join(character.name for character in list_characters_for_scene(session, scene.id))
    location_names = ", ".join(location.name for location in list_locations_for_scene(session, scene.id))

    sections = [
        f"# Scene: {scene.heading or '(untitled)'}",
        f"## Target Length\n\n{scene.target_length or '(unspecified)'}",
        f"## Brief\n\n{scene.brief}",
        f"## Locations\n\n{location_names or '(none)'}",
        f"## Characters\n\n{character_names or '(none)'}",
        f"## Required Elements\n\n{scene.required_actions or '(none)'}",
    ]
    if scene.desired_outcome:
        sections.append(f"## Desired Outcome\n\n{scene.desired_outcome}")
    if scene.pov_character_id is not None:
        pov_character = get_character(session, scene.pov_character_id)
        if pov_character is not None:
            sections.append(f"## Point of View\n\nWrite from {pov_character.name}'s point of view.")
    return "\n\n".join(sections)


def _character_roster_markdown(session: Session, story_id: int) -> str:
    characters = list_characters(session, story_id)
    if not characters:
        return "## Characters\n\n(none)"
    lines = ["## Characters", ""]
    for character in characters:
        description = character.description or "(no description)"
        motive = character.motive or "(none)"
        lines.append(f"- **{character.name}**: {description} (Motive: {motive})")
    return "\n".join(lines)


def _location_roster_markdown(session: Session, story_id: int) -> str:
    locations = list_locations(session, story_id)
    if not locations:
        return "## Locations\n\n(none)"
    lines = ["## Locations", ""]
    for location in locations:
        lines.append(f"- **{location.name}**: {location.description or '(no description)'}")
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

    fiction_prefix = (
        "You are a fiction writer drafting a scene of an ongoing story. This is a work of "
        "fiction: the story brief and this scene's details have already been laid out ahead "
        "of time by the story's author, so treat them as established facts of the story "
        "world rather than something to invent, question, or reconsider. Your job is only to "
        "write the requested scene's prose."
    )
    fiction_suffix = (
        "The story's author will give you one scene at a time, in the order that they will "
        "appear in the larger story. You will need to complete the scene so that the next "
        "scene of the story can be written. It is important that you include all required "
        "elements—they are intended to provide the spine of continuity for the story."
    )
    system_lines = [fiction_prefix, f"## Story Brief\n\n{story.story_brief}"]
    if story.style_guidance:
        system_lines.append(f"## Style Guidance\n\n{story.style_guidance}")
    if story.generation_guideance:
        system_lines.append(f"## Generation Guidance\n\n{story.generation_guideance}")
    system_lines.append(_character_roster_markdown(session, story_id))
    system_lines.append(_location_roster_markdown(session, story_id))
    system_lines.append(fiction_suffix)
    messages: list[dict[str, Any]] = [{"role": "system", "content": "\n\n".join(system_lines)}]

    for scene in scenes:
        if scene.position >= target.position:
            continue
        messages.append({"role": "user", "content": _scene_detail_text(session, scene)})
        messages.append({"role": "assistant", "content": _active_rendering_body(session, scene)})

    messages.append({"role": "user", "content": _scene_detail_text(session, target)})
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
