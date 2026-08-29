from sqlalchemy import select
from sqlalchemy.orm import Session

from scene.data.continuity_snapshot import ContinuitySnapshot
from scene.data.scene import Scene


def create_snapshot(
    session: Session,
    story_id: int,
    through_scene_id: int,
    narrative_state: str,
    narrative_state_reasoning: str | None = None,
) -> ContinuitySnapshot:
    scene = session.get(Scene, through_scene_id)
    if scene is None:
        raise ValueError(f"Scene {through_scene_id} not found")
    if scene.story_id != story_id:
        raise ValueError(f"Scene {through_scene_id} does not belong to story {story_id}")
    if get_snapshot(session, story_id, through_scene_id) is not None:
        raise ValueError(f"A continuity snapshot for story {story_id} through scene {through_scene_id} already exists")

    snapshot = ContinuitySnapshot(
        story_id=story_id,
        through_scene_id=through_scene_id,
        narrative_state=narrative_state,
        narrative_state_reasoning=narrative_state_reasoning,
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


def get_snapshot(session: Session, story_id: int, through_scene_id: int) -> ContinuitySnapshot | None:
    statement = select(ContinuitySnapshot).where(
        ContinuitySnapshot.story_id == story_id, ContinuitySnapshot.through_scene_id == through_scene_id
    )
    return session.scalars(statement).one_or_none()


def get_preceding_snapshot(session: Session, story_id: int, scene_id: int) -> ContinuitySnapshot | None:
    scenes = list(
        session.scalars(select(Scene).where(Scene.story_id == story_id).order_by(Scene.position))
    )
    target = next((scene for scene in scenes if scene.id == scene_id), None)
    if target is None:
        return None

    for scene in reversed([scene for scene in scenes if scene.position < target.position]):
        snapshot = get_snapshot(session, story_id, scene.id)
        if snapshot is not None:
            return snapshot
    return None


def invalidate_snapshots_from(session: Session, story_id: int, from_position: int) -> int:
    scene_ids = list(
        session.scalars(
            select(Scene.id).where(Scene.story_id == story_id, Scene.position >= from_position)
        )
    )
    if not scene_ids:
        return 0

    statement = select(ContinuitySnapshot).where(
        ContinuitySnapshot.story_id == story_id, ContinuitySnapshot.through_scene_id.in_(scene_ids)
    )
    snapshots = list(session.scalars(statement))
    for snapshot in snapshots:
        session.delete(snapshot)
    session.commit()
    return len(snapshots)


def delete_snapshot(session: Session, story_id: int, through_scene_id: int) -> bool:
    snapshot = get_snapshot(session, story_id, through_scene_id)
    if snapshot is None:
        return False
    session.delete(snapshot)
    session.commit()
    return True
