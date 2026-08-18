from sqlalchemy import select
from sqlalchemy.orm import Session

from scene.data.location import Location


def create_location(session: Session, story_id: int, name: str, description: str | None = None) -> Location:
    location = Location(story_id=story_id, name=name, description=description)
    session.add(location)
    session.commit()
    session.refresh(location)
    return location


def get_location(session: Session, location_id: int) -> Location | None:
    return session.get(Location, location_id)


def list_locations(session: Session, story_id: int) -> list[Location]:
    statement = select(Location).where(Location.story_id == story_id).order_by(Location.id)
    return list(session.scalars(statement))


def update_location(
    session: Session,
    location_id: int,
    name: str | None = None,
    description: str | None = None,
) -> Location | None:
    location = get_location(session, location_id)
    if location is None:
        return None
    if name is not None:
        location.name = name
    if description is not None:
        location.description = description
    session.commit()
    session.refresh(location)
    return location


def delete_location(session: Session, location_id: int) -> bool:
    location = get_location(session, location_id)
    if location is None:
        return False
    session.delete(location)
    session.commit()
    return True
