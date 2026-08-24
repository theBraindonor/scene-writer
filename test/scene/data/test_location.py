import pytest
from sqlalchemy.exc import IntegrityError

from scene.data.database import get_engine, get_session_factory, init_db
from scene.data.location import Location
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
        story = Story(title="A Title", story_brief="A story brief")
        session.add(story)
        session.commit()
        return story.id


def test_create_location(session_factory, story_id):
    with session_factory() as session:
        location = Location(story_id=story_id, name="Castle")
        session.add(location)
        session.commit()

        assert location.id is not None


def test_name_must_not_be_blank(session_factory, story_id):
    with session_factory() as session:
        session.add(Location(story_id=story_id, name="   "))
        with pytest.raises(IntegrityError):
            session.commit()


def test_name_must_be_unique_within_story(session_factory, story_id):
    with session_factory() as session:
        session.add(Location(story_id=story_id, name="Castle"))
        session.commit()

    with session_factory() as session:
        session.add(Location(story_id=story_id, name="Castle"))
        with pytest.raises(IntegrityError):
            session.commit()
