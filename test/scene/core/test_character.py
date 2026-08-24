import pytest

from scene.core.character import (
    create_character,
    delete_character,
    get_character,
    list_characters,
    update_character,
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


def test_create_and_get_character(session, story_id):
    character = create_character(session, story_id=story_id, name="Ada")

    fetched = get_character(session, character.id)

    assert fetched is not None
    assert fetched.name == "Ada"


def test_get_missing_character_returns_none(session):
    assert get_character(session, 999) is None


def test_list_characters_scoped_to_story(session, story_id):
    first = create_character(session, story_id=story_id, name="Ada")
    second = create_character(session, story_id=story_id, name="Bea")

    characters = list_characters(session, story_id)

    assert [character.id for character in characters] == [first.id, second.id]


def test_update_character(session, story_id):
    character = create_character(session, story_id=story_id, name="Ada")

    updated = update_character(session, character.id, name="Ada Lovelace", description="A pilot", motive="Escape")

    assert updated.name == "Ada Lovelace"
    assert updated.description == "A pilot"
    assert updated.motive == "Escape"


def test_update_missing_character_returns_none(session):
    assert update_character(session, 999, name="Updated") is None


def test_delete_character(session, story_id):
    character = create_character(session, story_id=story_id, name="Ada")

    deleted = delete_character(session, character.id)

    assert deleted is True
    assert get_character(session, character.id) is None


def test_delete_missing_character_returns_false(session):
    assert delete_character(session, 999) is False
