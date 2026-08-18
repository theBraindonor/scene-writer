from sqlalchemy import select
from sqlalchemy.orm import Session

from scene.data.location import Location
from scene.data.scene import Scene
from scene.data.scene_location import SceneLocation


def assign_location(session: Session, scene_id: int, location_id: int) -> SceneLocation:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"Scene {scene_id} not found")
    location = session.get(Location, location_id)
    if location is None:
        raise ValueError(f"Location {location_id} not found")
    if scene.story_id != location.story_id:
        raise ValueError(f"Scene {scene_id} and location {location_id} belong to different stories")

    assignment = SceneLocation(scene_id=scene_id, location_id=location_id)
    session.add(assignment)
    session.commit()
    return assignment


def unassign_location(session: Session, scene_id: int, location_id: int) -> bool:
    assignment = session.get(SceneLocation, (scene_id, location_id))
    if assignment is None:
        return False
    session.delete(assignment)
    session.commit()
    return True


def list_locations_for_scene(session: Session, scene_id: int) -> list[Location]:
    statement = (
        select(Location)
        .join(SceneLocation, SceneLocation.location_id == Location.id)
        .where(SceneLocation.scene_id == scene_id)
        .order_by(Location.id)
    )
    return list(session.scalars(statement))


def list_scenes_for_location(session: Session, location_id: int) -> list[Scene]:
    statement = (
        select(Scene)
        .join(SceneLocation, SceneLocation.scene_id == Scene.id)
        .where(SceneLocation.location_id == location_id)
        .order_by(Scene.id)
    )
    return list(session.scalars(statement))
