from sqlalchemy import select
from sqlalchemy.orm import Session

from scene.data.character import Character


def create_character(
    session: Session,
    story_id: int,
    name: str,
    description: str | None = None,
    motive: str | None = None,
) -> Character:
    character = Character(story_id=story_id, name=name, description=description, motive=motive)
    session.add(character)
    session.commit()
    session.refresh(character)
    return character


def get_character(session: Session, character_id: int) -> Character | None:
    return session.get(Character, character_id)


def list_characters(session: Session, story_id: int) -> list[Character]:
    statement = select(Character).where(Character.story_id == story_id).order_by(Character.id)
    return list(session.scalars(statement))


def update_character(
    session: Session,
    character_id: int,
    name: str | None = None,
    description: str | None = None,
    motive: str | None = None,
) -> Character | None:
    character = get_character(session, character_id)
    if character is None:
        return None
    if name is not None:
        character.name = name
    if description is not None:
        character.description = description
    if motive is not None:
        character.motive = motive
    session.commit()
    session.refresh(character)
    return character


def delete_character(session: Session, character_id: int) -> bool:
    character = get_character(session, character_id)
    if character is None:
        return False
    session.delete(character)
    session.commit()
    return True
