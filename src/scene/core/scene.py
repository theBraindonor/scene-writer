from sqlalchemy import select
from sqlalchemy.orm import Session

from scene.data.scene import Scene


def create_scene(
    session: Session,
    story_id: int,
    position: int,
    description: str,
    heading: str | None = None,
    required_actions: str | None = None,
) -> Scene:
    scene = Scene(
        story_id=story_id,
        position=position,
        description=description,
        heading=heading,
        required_actions=required_actions,
    )
    session.add(scene)
    session.commit()
    session.refresh(scene)
    return scene


def get_scene(session: Session, scene_id: int) -> Scene | None:
    return session.get(Scene, scene_id)


def list_scenes(session: Session, story_id: int) -> list[Scene]:
    statement = select(Scene).where(Scene.story_id == story_id).order_by(Scene.position)
    return list(session.scalars(statement))


def update_scene(
    session: Session,
    scene_id: int,
    position: int | None = None,
    heading: str | None = None,
    description: str | None = None,
    required_actions: str | None = None,
) -> Scene | None:
    scene = get_scene(session, scene_id)
    if scene is None:
        return None
    if position is not None:
        scene.position = position
    if heading is not None:
        scene.heading = heading
    if description is not None:
        scene.description = description
    if required_actions is not None:
        scene.required_actions = required_actions
    session.commit()
    session.refresh(scene)
    return scene


def delete_scene(session: Session, scene_id: int) -> bool:
    scene = get_scene(session, scene_id)
    if scene is None:
        return False
    session.delete(scene)
    session.commit()
    return True
