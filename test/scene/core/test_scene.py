import pytest

from scene.core.character import create_character
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
    story = create_story(session, title="Title", story_brief="Story brief")
    return story.id


@pytest.fixture
def character_id(session, story_id):
    character = create_character(session, story_id=story_id, name="Ada")
    return character.id


def test_create_and_get_scene(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="A brief")

    fetched = get_scene(session, scene.id)

    assert fetched is not None
    assert fetched.brief == "A brief"
    assert fetched.target_length is None
    assert fetched.desired_outcome is None
    assert fetched.pov_character_id is None


def test_get_missing_scene_returns_none(session):
    assert get_scene(session, 999) is None


def test_list_scenes_scoped_to_story_ordered_by_position(session, story_id):
    second = create_scene(session, story_id=story_id, position=1, brief="Second")
    first = create_scene(session, story_id=story_id, position=0, brief="First")

    scenes = list_scenes(session, story_id)

    assert [scene.id for scene in scenes] == [first.id, second.id]


def test_update_scene(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="Original")

    updated = update_scene(session, scene.id, brief="Updated")

    assert updated.brief == "Updated"
    assert updated.position == 0


def test_update_scene_position_heading_and_required_actions(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="Original")

    updated = update_scene(
        session,
        scene.id,
        position=1,
        heading="New Heading",
        required_actions="Run away",
        target_length="about 800 characters",
    )

    assert updated.position == 1
    assert updated.heading == "New Heading"
    assert updated.required_actions == "Run away"
    assert updated.target_length == "about 800 characters"
    assert updated.brief == "Original"


def test_create_scene_with_target_length(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="Original", target_length="short")

    assert scene.target_length == "short"


def test_create_scene_with_desired_outcome(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="Original", desired_outcome="Mara escapes")

    assert scene.desired_outcome == "Mara escapes"


def test_update_scene_desired_outcome(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="Original")

    updated = update_scene(session, scene.id, desired_outcome="Mara escapes")

    assert updated.desired_outcome == "Mara escapes"


def test_create_scene_with_pov_character(session, story_id, character_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="Original", pov_character_id=character_id)

    assert scene.pov_character_id == character_id


def test_create_scene_with_missing_pov_character_raises(session, story_id):
    with pytest.raises(ValueError, match="Character 999 not found"):
        create_scene(session, story_id=story_id, position=0, brief="Original", pov_character_id=999)


def test_create_scene_with_cross_story_pov_character_raises(session, story_id):
    other_story = create_story(session, title="Other", story_brief="Other story brief")
    other_character = create_character(session, story_id=other_story.id, name="Bea")

    with pytest.raises(ValueError, match="does not belong to story"):
        create_scene(session, story_id=story_id, position=0, brief="Original", pov_character_id=other_character.id)


def test_update_scene_with_pov_character(session, story_id, character_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="Original")

    updated = update_scene(session, scene.id, pov_character_id=character_id)

    assert updated.pov_character_id == character_id


def test_update_scene_with_cross_story_pov_character_raises(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="Original")
    other_story = create_story(session, title="Other", story_brief="Other story brief")
    other_character = create_character(session, story_id=other_story.id, name="Bea")

    with pytest.raises(ValueError, match="does not belong to story"):
        update_scene(session, scene.id, pov_character_id=other_character.id)


def test_update_missing_scene_returns_none(session):
    assert update_scene(session, 999, brief="Updated") is None


def test_delete_scene(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="A brief")

    deleted = delete_scene(session, scene.id)

    assert deleted is True
    assert get_scene(session, scene.id) is None


def test_delete_missing_scene_returns_false(session):
    assert delete_scene(session, 999) is False
