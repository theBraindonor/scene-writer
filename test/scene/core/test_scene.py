import pytest

from scene.core.scene import create_scene, delete_scene, get_scene, list_scenes, update_scene
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
    story = create_story(session, title="Title", scenario="Scenario")
    return story.id


def test_create_and_get_scene(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, description="A description")

    fetched = get_scene(session, scene.id)

    assert fetched is not None
    assert fetched.description == "A description"


def test_get_missing_scene_returns_none(session):
    assert get_scene(session, 999) is None


def test_list_scenes_scoped_to_story_ordered_by_position(session, story_id):
    second = create_scene(session, story_id=story_id, position=1, description="Second")
    first = create_scene(session, story_id=story_id, position=0, description="First")

    scenes = list_scenes(session, story_id)

    assert [scene.id for scene in scenes] == [first.id, second.id]


def test_update_scene(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, description="Original")

    updated = update_scene(session, scene.id, description="Updated")

    assert updated.description == "Updated"
    assert updated.position == 0


def test_update_scene_position_heading_and_required_actions(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, description="Original")

    updated = update_scene(
        session,
        scene.id,
        position=1,
        heading="New Heading",
        required_actions="Run away",
        length="about 800 characters",
    )

    assert updated.position == 1
    assert updated.heading == "New Heading"
    assert updated.required_actions == "Run away"
    assert updated.length == "about 800 characters"
    assert updated.description == "Original"


def test_create_scene_with_length(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, description="Original", length="short")

    assert scene.length == "short"


def test_update_missing_scene_returns_none(session):
    assert update_scene(session, 999, description="Updated") is None


def test_delete_scene(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, description="A description")

    deleted = delete_scene(session, scene.id)

    assert deleted is True
    assert get_scene(session, scene.id) is None


def test_delete_missing_scene_returns_false(session):
    assert delete_scene(session, 999) is False
