import pytest
from sqlalchemy.exc import IntegrityError

from scene.data.character import Character
from scene.data.database import get_engine, get_session_factory, init_db
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


def test_create_character(session_factory, story_id):
    with session_factory() as session:
        character = Character(story_id=story_id, name="Ada")
        session.add(character)
        session.commit()

        assert character.id is not None


def test_name_must_not_be_blank(session_factory, story_id):
    with session_factory() as session:
        session.add(Character(story_id=story_id, name="   "))
        with pytest.raises(IntegrityError):
            session.commit()


def test_name_must_be_unique_within_story(session_factory, story_id):
    with session_factory() as session:
        session.add(Character(story_id=story_id, name="Ada"))
        session.commit()

    with session_factory() as session:
        session.add(Character(story_id=story_id, name="Ada"))
        with pytest.raises(IntegrityError):
            session.commit()
