from sqlalchemy import select, update
from sqlalchemy.orm import Session

from scene.data.rendering import Rendering


def create_rendering(session: Session, scene_id: int, body: str, body_reasoning: str | None = None) -> Rendering:
    rendering = Rendering(scene_id=scene_id, body=body, body_reasoning=body_reasoning)
    session.add(rendering)
    session.commit()
    session.refresh(rendering)
    return rendering


def get_rendering(session: Session, rendering_id: int) -> Rendering | None:
    return session.get(Rendering, rendering_id)


def list_renderings(session: Session, scene_id: int) -> list[Rendering]:
    statement = select(Rendering).where(Rendering.scene_id == scene_id).order_by(Rendering.id)
    return list(session.scalars(statement))


def set_active_rendering(session: Session, rendering_id: int) -> Rendering | None:
    rendering = get_rendering(session, rendering_id)
    if rendering is None:
        return None
    session.execute(
        update(Rendering)
        .where(Rendering.scene_id == rendering.scene_id, Rendering.id != rendering.id)
        .values(is_active=0)
    )
    session.flush()
    rendering.is_active = 1
    session.commit()
    session.refresh(rendering)
    return rendering


def delete_rendering(session: Session, rendering_id: int) -> bool:
    rendering = get_rendering(session, rendering_id)
    if rendering is None:
        return False
    session.delete(rendering)
    session.commit()
    return True
