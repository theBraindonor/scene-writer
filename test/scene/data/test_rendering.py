import pytest
from sqlalchemy.exc import IntegrityError

from scene.data.database import get_engine, get_session_factory, init_db
from scene.data.rendering import Rendering
from scene.data.scene import Scene
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
def scene_id(session_factory):
    with session_factory() as session:
        story = Story(title="A Title", scenario="A scenario")
        session.add(story)
        session.commit()
        scene = Scene(story_id=story.id, position=0, description="A description")
        session.add(scene)
        session.commit()
        return scene.id


def test_create_rendering(session_factory, scene_id):
    with session_factory() as session:
        rendering = Rendering(scene_id=scene_id, body="Some prose")
        session.add(rendering)
        session.commit()

        assert rendering.id is not None
        assert rendering.is_active == 0


def test_is_active_must_be_boolean(session_factory, scene_id):
    with session_factory() as session:
        session.add(Rendering(scene_id=scene_id, body="Some prose", is_active=2))
        with pytest.raises(IntegrityError):
            session.commit()


def test_only_one_active_rendering_per_scene(session_factory, scene_id):
    with session_factory() as session:
        session.add(Rendering(scene_id=scene_id, body="First", is_active=1))
        session.commit()

    with session_factory() as session:
        session.add(Rendering(scene_id=scene_id, body="Second", is_active=1))
        with pytest.raises(IntegrityError):
            session.commit()
