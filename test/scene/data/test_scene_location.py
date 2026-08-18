import pytest
from sqlalchemy.exc import IntegrityError

from scene.data.database import get_engine, get_session_factory, init_db
from scene.data.location import Location
from scene.data.scene import Scene
from scene.data.scene_location import SceneLocation
from scene.data.story import Story


@pytest.fixture
def session_factory():
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    try:
        yield get_session_factory(engine)
    finally:
        engine.dispose()


@pytest.fixture
def scene_and_location_id(session_factory):
    with session_factory() as session:
        story = Story(title="A Title", scenario="A scenario")
        session.add(story)
        session.commit()
        scene = Scene(story_id=story.id, position=0, description="A description")
        location = Location(story_id=story.id, name="Castle")
        session.add_all([scene, location])
        session.commit()
        return scene.id, location.id


def test_create_assignment(session_factory, scene_and_location_id):
    scene_id, location_id = scene_and_location_id
    with session_factory() as session:
        session.add(SceneLocation(scene_id=scene_id, location_id=location_id))
        session.commit()

        assert session.get(SceneLocation, (scene_id, location_id)) is not None


def test_duplicate_assignment_raises(session_factory, scene_and_location_id):
    scene_id, location_id = scene_and_location_id
    with session_factory() as session:
        session.add(SceneLocation(scene_id=scene_id, location_id=location_id))
        session.commit()

    with session_factory() as session:
        session.add(SceneLocation(scene_id=scene_id, location_id=location_id))
        with pytest.raises(IntegrityError):
            session.commit()
