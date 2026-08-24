import pytest

from scene.core.location import create_location
from scene.core.scene import create_scene
from scene.core.scene_location import (
    assign_location,
    list_locations_for_scene,
    list_scenes_for_location,
    unassign_location,
)
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


@pytest.fixture
def scene_id(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="A brief")
    return scene.id


@pytest.fixture
def location_id(session, story_id):
    location = create_location(session, story_id=story_id, name="Castle")
    return location.id


def test_assign_and_list_locations_for_scene(session, scene_id, location_id):
    assign_location(session, scene_id=scene_id, location_id=location_id)

    locations = list_locations_for_scene(session, scene_id)

    assert [location.id for location in locations] == [location_id]


def test_assign_and_list_scenes_for_location(session, scene_id, location_id):
    assign_location(session, scene_id=scene_id, location_id=location_id)

    scenes = list_scenes_for_location(session, location_id)

    assert [scene.id for scene in scenes] == [scene_id]


def test_assign_missing_scene_raises(session, location_id):
    with pytest.raises(ValueError, match="Scene 999 not found"):
        assign_location(session, scene_id=999, location_id=location_id)


def test_assign_missing_location_raises(session, scene_id):
    with pytest.raises(ValueError, match="Location 999 not found"):
        assign_location(session, scene_id=scene_id, location_id=999)


def test_assign_cross_story_raises(session, scene_id):
    other_story = create_story(session, title="Other", story_brief="Other story brief")
    other_location = create_location(session, story_id=other_story.id, name="Forest")

    with pytest.raises(ValueError, match="different stories"):
        assign_location(session, scene_id=scene_id, location_id=other_location.id)


def test_unassign_location(session, scene_id, location_id):
    assign_location(session, scene_id=scene_id, location_id=location_id)

    unassigned = unassign_location(session, scene_id=scene_id, location_id=location_id)

    assert unassigned is True
    assert list_locations_for_scene(session, scene_id) == []


def test_unassign_missing_assignment_returns_false(session, scene_id, location_id):
    assert unassign_location(session, scene_id=scene_id, location_id=location_id) is False
