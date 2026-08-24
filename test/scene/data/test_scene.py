import pytest
from sqlalchemy.exc import IntegrityError

from scene.data.character import Character
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
        story = Story(title="A Title", story_brief="A story brief")
        session.add(story)
        session.commit()
        return story.id


@pytest.fixture
def character_id(session_factory, story_id):
    with session_factory() as session:
        character = Character(story_id=story_id, name="Ada")
        session.add(character)
        session.commit()
        return character.id


def test_create_scene(session_factory, story_id):
    with session_factory() as session:
        scene = Scene(story_id=story_id, position=0, brief="A brief")
        session.add(scene)
        session.commit()

        assert scene.id is not None
        assert scene.target_length is None
        assert scene.desired_outcome is None
        assert scene.pov_character_id is None


def test_create_scene_with_target_length(session_factory, story_id):
    with session_factory() as session:
        scene = Scene(story_id=story_id, position=0, brief="A brief", target_length="about 800 characters")
        session.add(scene)
        session.commit()

        assert scene.target_length == "about 800 characters"


def test_create_scene_with_desired_outcome(session_factory, story_id):
    with session_factory() as session:
        scene = Scene(story_id=story_id, position=0, brief="A brief", desired_outcome="Mara finds the map")
        session.add(scene)
        session.commit()

        assert scene.desired_outcome == "Mara finds the map"


def test_create_scene_with_pov_character(session_factory, story_id, character_id):
    with session_factory() as session:
        scene = Scene(story_id=story_id, position=0, brief="A brief", pov_character_id=character_id)
        session.add(scene)
        session.commit()

        assert scene.pov_character_id == character_id


def test_position_must_be_non_negative(session_factory, story_id):
    with session_factory() as session:
        session.add(Scene(story_id=story_id, position=-1, brief="A brief"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_brief_must_not_be_blank(session_factory, story_id):
    with session_factory() as session:
        session.add(Scene(story_id=story_id, position=0, brief="   "))
        with pytest.raises(IntegrityError):
            session.commit()


def test_position_must_be_unique_within_story(session_factory, story_id):
    with session_factory() as session:
        session.add(Scene(story_id=story_id, position=0, brief="First"))
        session.commit()

    with session_factory() as session:
        session.add(Scene(story_id=story_id, position=0, brief="Second"))
        with pytest.raises(IntegrityError):
            session.commit()
