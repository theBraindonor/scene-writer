import pytest

from scene.core.character import create_character
from scene.core.scene import create_scene
from scene.core.scene_character import (
    assign_character,
    list_characters_for_scene,
    list_scenes_for_character,
    unassign_character,
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
def character_id(session, story_id):
    character = create_character(session, story_id=story_id, name="Ada")
    return character.id


def test_assign_and_list_characters_for_scene(session, scene_id, character_id):
    assign_character(session, scene_id=scene_id, character_id=character_id)

    characters = list_characters_for_scene(session, scene_id)

    assert [character.id for character in characters] == [character_id]


def test_assign_and_list_scenes_for_character(session, scene_id, character_id):
    assign_character(session, scene_id=scene_id, character_id=character_id)

    scenes = list_scenes_for_character(session, character_id)

    assert [scene.id for scene in scenes] == [scene_id]


def test_assign_missing_scene_raises(session, character_id):
    with pytest.raises(ValueError, match="Scene 999 not found"):
        assign_character(session, scene_id=999, character_id=character_id)


def test_assign_missing_character_raises(session, scene_id):
    with pytest.raises(ValueError, match="Character 999 not found"):
        assign_character(session, scene_id=scene_id, character_id=999)


def test_assign_cross_story_raises(session, scene_id):
    other_story = create_story(session, title="Other", story_brief="Other story brief")
    other_character = create_character(session, story_id=other_story.id, name="Bea")

    with pytest.raises(ValueError, match="different stories"):
        assign_character(session, scene_id=scene_id, character_id=other_character.id)


def test_unassign_character(session, scene_id, character_id):
    assign_character(session, scene_id=scene_id, character_id=character_id)

    unassigned = unassign_character(session, scene_id=scene_id, character_id=character_id)

    assert unassigned is True
    assert list_characters_for_scene(session, scene_id) == []


def test_unassign_missing_assignment_returns_false(session, scene_id, character_id):
    assert unassign_character(session, scene_id=scene_id, character_id=character_id) is False
