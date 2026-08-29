import pytest

from scene.core.rendering import (
    create_rendering,
    delete_rendering,
    get_rendering,
    list_renderings,
    set_active_rendering,
)
from scene.core.scene import create_scene
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
def scene_id(session):
    story = create_story(session, title="Title", story_brief="Story brief")
    scene = create_scene(session, story_id=story.id, position=0, brief="A brief")
    return scene.id


def test_create_and_get_rendering(session, scene_id):
    rendering = create_rendering(session, scene_id=scene_id, body="Some prose")

    fetched = get_rendering(session, rendering.id)

    assert fetched is not None
    assert fetched.body == "Some prose"
    assert fetched.is_active == 0
    assert fetched.body_reasoning is None


def test_create_rendering_with_reasoning(session, scene_id):
    rendering = create_rendering(
        session, scene_id=scene_id, body="Some prose", body_reasoning="Considered the scene brief."
    )

    fetched = get_rendering(session, rendering.id)

    assert fetched.body_reasoning == "Considered the scene brief."


def test_get_missing_rendering_returns_none(session):
    assert get_rendering(session, 999) is None


def test_list_renderings_scoped_to_scene(session, scene_id):
    first = create_rendering(session, scene_id=scene_id, body="First")
    second = create_rendering(session, scene_id=scene_id, body="Second")

    renderings = list_renderings(session, scene_id)

    assert [rendering.id for rendering in renderings] == [first.id, second.id]


def test_set_active_rendering_deactivates_others(session, scene_id):
    first = create_rendering(session, scene_id=scene_id, body="First")
    second = create_rendering(session, scene_id=scene_id, body="Second")

    set_active_rendering(session, first.id)
    activated = set_active_rendering(session, second.id)

    assert activated.is_active == 1
    assert get_rendering(session, first.id).is_active == 0


def test_set_active_missing_rendering_returns_none(session):
    assert set_active_rendering(session, 999) is None


def test_delete_rendering(session, scene_id):
    rendering = create_rendering(session, scene_id=scene_id, body="Some prose")

    deleted = delete_rendering(session, rendering.id)

    assert deleted is True
    assert get_rendering(session, rendering.id) is None


def test_delete_missing_rendering_returns_false(session):
    assert delete_rendering(session, 999) is False
