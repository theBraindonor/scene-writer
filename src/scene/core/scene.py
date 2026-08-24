from sqlalchemy import select
from sqlalchemy.orm import Session

from scene.data.character import Character
from scene.data.scene import Scene


def _validate_pov_character(session: Session, story_id: int, pov_character_id: int) -> None:
    character = session.get(Character, pov_character_id)
    if character is None:
        raise ValueError(f"Character {pov_character_id} not found")
    if character.story_id != story_id:
        raise ValueError(f"Character {pov_character_id} does not belong to story {story_id}")


def create_scene(
    session: Session,
    story_id: int,
    position: int,
    brief: str,
    heading: str | None = None,
    required_actions: str | None = None,
    target_length: str | None = None,
    desired_outcome: str | None = None,
    pov_character_id: int | None = None,
) -> Scene:
    if pov_character_id is not None:
        _validate_pov_character(session, story_id, pov_character_id)

    scene = Scene(
        story_id=story_id,
        position=position,
        brief=brief,
        heading=heading,
        required_actions=required_actions,
        target_length=target_length,
        desired_outcome=desired_outcome,
        pov_character_id=pov_character_id,
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
    brief: str | None = None,
    required_actions: str | None = None,
    target_length: str | None = None,
    desired_outcome: str | None = None,
    pov_character_id: int | None = None,
) -> Scene | None:
    scene = get_scene(session, scene_id)
    if scene is None:
        return None
    if pov_character_id is not None:
        _validate_pov_character(session, scene.story_id, pov_character_id)
    if position is not None:
        scene.position = position
    if heading is not None:
        scene.heading = heading
    if brief is not None:
        scene.brief = brief
    if required_actions is not None:
        scene.required_actions = required_actions
    if target_length is not None:
        scene.target_length = target_length
    if desired_outcome is not None:
        scene.desired_outcome = desired_outcome
    if pov_character_id is not None:
        scene.pov_character_id = pov_character_id
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
