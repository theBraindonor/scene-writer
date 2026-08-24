import pytest

from scene.core.location import create_location, delete_location, get_location, list_locations, update_location
from scene.core.story import create_story
from scene.data.database import get_engine, get_session_factory, init_db


@pytest.fixture
def session():
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    try:
        with get_session_factory(engine)() as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def story_id(session):
    story = create_story(session, title="Title", story_brief="Story brief")
    return story.id


def test_create_and_get_location(session, story_id):
    location = create_location(session, story_id=story_id, name="Castle")

    fetched = get_location(session, location.id)

    assert fetched is not None
    assert fetched.name == "Castle"


def test_get_missing_location_returns_none(session):
    assert get_location(session, 999) is None


def test_list_locations_scoped_to_story(session, story_id):
    first = create_location(session, story_id=story_id, name="Castle")
    second = create_location(session, story_id=story_id, name="Forest")

    locations = list_locations(session, story_id)

    assert [location.id for location in locations] == [first.id, second.id]


def test_update_location(session, story_id):
    location = create_location(session, story_id=story_id, name="Castle")

    updated = update_location(session, location.id, name="Old Castle", description="A ruin")

    assert updated.name == "Old Castle"
    assert updated.description == "A ruin"


def test_update_missing_location_returns_none(session):
    assert update_location(session, 999, name="Updated") is None


def test_delete_location(session, story_id):
    location = create_location(session, story_id=story_id, name="Castle")

    deleted = delete_location(session, location.id)

    assert deleted is True
    assert get_location(session, location.id) is None


def test_delete_missing_location_returns_false(session):
    assert delete_location(session, 999) is False
