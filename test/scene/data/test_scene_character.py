import pytest
from sqlalchemy.exc import IntegrityError

from scene.data.character import Character
from scene.data.database import get_engine, get_session_factory, init_db
from scene.data.scene import Scene
from scene.data.scene_character import SceneCharacter
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
def scene_and_character_id(session_factory):
    with session_factory() as session:
        story = Story(title="A Title", scenario="A scenario")
        session.add(story)
        session.commit()
        scene = Scene(story_id=story.id, position=0, description="A description")
        character = Character(story_id=story.id, name="Ada")
        session.add_all([scene, character])
        session.commit()
        return scene.id, character.id


def test_create_assignment(session_factory, scene_and_character_id):
    scene_id, character_id = scene_and_character_id
    with session_factory() as session:
        session.add(SceneCharacter(scene_id=scene_id, character_id=character_id))
        session.commit()

        assert session.get(SceneCharacter, (scene_id, character_id)) is not None


def test_duplicate_assignment_raises(session_factory, scene_and_character_id):
    scene_id, character_id = scene_and_character_id
    with session_factory() as session:
        session.add(SceneCharacter(scene_id=scene_id, character_id=character_id))
        session.commit()

    with session_factory() as session:
        session.add(SceneCharacter(scene_id=scene_id, character_id=character_id))
        with pytest.raises(IntegrityError):
            session.commit()
