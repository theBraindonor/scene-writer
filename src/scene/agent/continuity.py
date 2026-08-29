from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from scene.agent.config import LLMConfig
from scene.agent.llm import complete, stream_complete
from scene.agent.prompts import load_prompts
from scene.core.continuity_snapshot import (
    create_snapshot,
    delete_snapshot,
    get_preceding_snapshot,
    invalidate_snapshots_from,
)
from scene.core.rendering import list_renderings
from scene.core.scene import list_scenes
from scene.data.continuity_snapshot import ContinuitySnapshot

NO_PRIOR_NARRATIVE_STATE = "(No prior narrative state; this is the first scene.)"

CONTINUITY_EDITOR_SYSTEM_PROMPT = load_prompts().continuity_editor_system_prompt


def _active_rendering_body(session: Session, scene_id: int) -> str:
    active = next((rendering for rendering in list_renderings(session, scene_id) if rendering.is_active), None)
    if active is None:
        raise ValueError(f"Scene {scene_id} has no active rendering.")
    return active.body


def build_continuity_messages(session: Session, story_id: int, scene_id: int) -> list[dict[str, Any]]:
    accepted_scene_body = _active_rendering_body(session, scene_id)
    preceding = get_preceding_snapshot(session, story_id, scene_id)
    prior_narrative_state = preceding.narrative_state if preceding is not None else NO_PRIOR_NARRATIVE_STATE

    user_content = (
        f"CURRENT CANONICAL NARRATIVE STATE\n{prior_narrative_state}\n\nACCEPTED SCENE\n{accepted_scene_body}"
    )
    return [
        {"role": "system", "content": CONTINUITY_EDITOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


@dataclass(frozen=True)
class ContinuityEditResult:
    narrative_state: str
    narrative_state_reasoning: str = ""


def run_continuity_edit(config: LLMConfig, messages: list[dict[str, Any]]) -> ContinuityEditResult:
    response = complete(config, messages)
    message = response.choices[0].message
    return ContinuityEditResult(
        narrative_state=message.content,
        narrative_state_reasoning=getattr(message, "reasoning_content", None) or "",
    )


def accept_scene(config: LLMConfig, session: Session, story_id: int, scene_id: int) -> ContinuitySnapshot:
    messages = build_continuity_messages(session, story_id, scene_id)
    result = run_continuity_edit(config, messages)
    delete_snapshot(session, story_id, scene_id)
    return create_snapshot(
        session,
        story_id,
        scene_id,
        result.narrative_state,
        narrative_state_reasoning=result.narrative_state_reasoning or None,
    )


def regenerate_snapshots_from(config: LLMConfig, session: Session, story_id: int, from_position: int) -> None:
    invalidate_snapshots_from(session, story_id, from_position)
    for scene in list_scenes(session, story_id):
        if scene.position < from_position:
            continue
        renderings = list_renderings(session, scene.id)
        if not any(rendering.is_active for rendering in renderings):
            break
        accept_scene(config, session, story_id, scene.id)


@dataclass(frozen=True)
class ContinuityReasoningDelta:
    text: str


@dataclass(frozen=True)
class ContinuityContentDelta:
    text: str


@dataclass(frozen=True)
class ContinuityComplete:
    text: str
    reasoning: str = ""


@dataclass(frozen=True)
class ContinuitySceneStarted:
    scene_id: int


@dataclass(frozen=True)
class ContinuitySceneComplete:
    scene_id: int
    snapshot: ContinuitySnapshot


ContinuityEvent = (
    ContinuityReasoningDelta
    | ContinuityContentDelta
    | ContinuityComplete
    | ContinuitySceneStarted
    | ContinuitySceneComplete
)


def stream_continuity_edit(config: LLMConfig, messages: list[dict[str, Any]]) -> Iterator[ContinuityEvent]:
    content_parts: list[str] = []
    reasoning_parts: list[str] = []

    for chunk in stream_complete(config, messages):
        delta = chunk.choices[0].delta

        reasoning_piece = getattr(delta, "reasoning_content", None)
        if reasoning_piece:
            reasoning_parts.append(reasoning_piece)
            yield ContinuityReasoningDelta(reasoning_piece)

        content_piece = getattr(delta, "content", None)
        if content_piece:
            content_parts.append(content_piece)
            yield ContinuityContentDelta(content_piece)

    yield ContinuityComplete(text="".join(content_parts), reasoning="".join(reasoning_parts))


def stream_accept_scene(config: LLMConfig, session: Session, story_id: int, scene_id: int) -> Iterator[ContinuityEvent]:
    messages = build_continuity_messages(session, story_id, scene_id)
    yield ContinuitySceneStarted(scene_id)
    for event in stream_continuity_edit(config, messages):
        if isinstance(event, ContinuityComplete):
            delete_snapshot(session, story_id, scene_id)
            snapshot = create_snapshot(
                session, story_id, scene_id, event.text, narrative_state_reasoning=event.reasoning or None
            )
            yield ContinuitySceneComplete(scene_id, snapshot)
        else:
            yield event


def stream_regenerate_snapshots_from(
    config: LLMConfig, session: Session, story_id: int, from_position: int
) -> Iterator[ContinuityEvent]:
    invalidate_snapshots_from(session, story_id, from_position)
    for scene in list_scenes(session, story_id):
        if scene.position < from_position:
            continue
        renderings = list_renderings(session, scene.id)
        if not any(rendering.is_active for rendering in renderings):
            break
        yield from stream_accept_scene(config, session, story_id, scene.id)
