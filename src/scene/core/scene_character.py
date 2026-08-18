from sqlalchemy import select
from sqlalchemy.orm import Session

from scene.data.character import Character
from scene.data.scene import Scene
from scene.data.scene_character import SceneCharacter


def assign_character(session: Session, scene_id: int, character_id: int) -> SceneCharacter:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"Scene {scene_id} not found")
    character = session.get(Character, character_id)
    if character is None:
        raise ValueError(f"Character {character_id} not found")
    if scene.story_id != character.story_id:
        raise ValueError(f"Scene {scene_id} and character {character_id} belong to different stories")

    assignment = SceneCharacter(scene_id=scene_id, character_id=character_id)
    session.add(assignment)
    session.commit()
    return assignment


def unassign_character(session: Session, scene_id: int, character_id: int) -> bool:
    assignment = session.get(SceneCharacter, (scene_id, character_id))
    if assignment is None:
        return False
    session.delete(assignment)
    session.commit()
    return True


def list_characters_for_scene(session: Session, scene_id: int) -> list[Character]:
    statement = (
        select(Character)
        .join(SceneCharacter, SceneCharacter.character_id == Character.id)
        .where(SceneCharacter.scene_id == scene_id)
        .order_by(Character.id)
    )
    return list(session.scalars(statement))


def list_scenes_for_character(session: Session, character_id: int) -> list[Scene]:
    statement = (
        select(Scene)
        .join(SceneCharacter, SceneCharacter.scene_id == Scene.id)
        .where(SceneCharacter.character_id == character_id)
        .order_by(Scene.id)
    )
    return list(session.scalars(statement))
