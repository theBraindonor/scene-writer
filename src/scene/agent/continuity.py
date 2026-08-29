from typing import Any

from sqlalchemy.orm import Session

from scene.agent.config import LLMConfig
from scene.agent.llm import complete
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


def run_continuity_edit(config: LLMConfig, messages: list[dict[str, Any]]) -> str:
    response = complete(config, messages)
    return response.choices[0].message.content


def accept_scene(config: LLMConfig, session: Session, story_id: int, scene_id: int) -> ContinuitySnapshot:
    messages = build_continuity_messages(session, story_id, scene_id)
    narrative_state = run_continuity_edit(config, messages)
    delete_snapshot(session, story_id, scene_id)
    return create_snapshot(session, story_id, scene_id, narrative_state)


def regenerate_snapshots_from(config: LLMConfig, session: Session, story_id: int, from_position: int) -> None:
    invalidate_snapshots_from(session, story_id, from_position)
    for scene in list_scenes(session, story_id):
        if scene.position < from_position:
            continue
        renderings = list_renderings(session, scene.id)
        if not any(rendering.is_active for rendering in renderings):
            break
        accept_scene(config, session, story_id, scene.id)
