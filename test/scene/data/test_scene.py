import pytest
from sqlalchemy.exc import IntegrityError

from scene.data.database import get_engine, get_session_factory, init_db
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
def story_id(session_factory):
    with session_factory() as session:
        story = Story(title="A Title", scenario="A scenario")
        session.add(story)
        session.commit()
        return story.id


def test_create_scene(session_factory, story_id):
    with session_factory() as session:
        scene = Scene(story_id=story_id, position=0, description="A description")
        session.add(scene)
        session.commit()

        assert scene.id is not None


def test_position_must_be_non_negative(session_factory, story_id):
    with session_factory() as session:
        session.add(Scene(story_id=story_id, position=-1, description="A description"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_description_must_not_be_blank(session_factory, story_id):
    with session_factory() as session:
        session.add(Scene(story_id=story_id, position=0, description="   "))
        with pytest.raises(IntegrityError):
            session.commit()


def test_position_must_be_unique_within_story(session_factory, story_id):
    with session_factory() as session:
        session.add(Scene(story_id=story_id, position=0, description="First"))
        session.commit()

    with session_factory() as session:
        session.add(Scene(story_id=story_id, position=0, description="Second"))
        with pytest.raises(IntegrityError):
            session.commit()
