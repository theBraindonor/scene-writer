import pytest
from sqlalchemy.exc import IntegrityError

from scene.data.character import Character  # noqa: F401 - registers Character for Scene.pov_character_id's FK
from scene.data.continuity_snapshot import ContinuitySnapshot
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
def scene_id(session_factory, story_id):
    with session_factory() as session:
        scene = Scene(story_id=story_id, position=0, brief="A brief")
        session.add(scene)
        session.commit()
        return scene.id


def test_create_continuity_snapshot(session_factory, story_id, scene_id):
    with session_factory() as session:
        snapshot = ContinuitySnapshot(
            story_id=story_id, through_scene_id=scene_id, narrative_state="Mara is at the station."
        )
        session.add(snapshot)
        session.commit()

        assert snapshot.id is not None


def test_narrative_state_must_not_be_blank(session_factory, story_id, scene_id):
    with session_factory() as session:
        session.add(ContinuitySnapshot(story_id=story_id, through_scene_id=scene_id, narrative_state="   "))
        with pytest.raises(IntegrityError):
            session.commit()


def test_story_id_through_scene_id_must_be_unique(session_factory, story_id, scene_id):
    with session_factory() as session:
        session.add(
            ContinuitySnapshot(story_id=story_id, through_scene_id=scene_id, narrative_state="First state")
        )
        session.commit()

    with session_factory() as session:
        session.add(
            ContinuitySnapshot(story_id=story_id, through_scene_id=scene_id, narrative_state="Second state")
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_deleting_story_cascades_to_continuity_snapshot(session_factory, story_id, scene_id):
    with session_factory() as session:
        snapshot = ContinuitySnapshot(
            story_id=story_id, through_scene_id=scene_id, narrative_state="Mara is at the station."
        )
        session.add(snapshot)
        session.commit()
        snapshot_id = snapshot.id

    with session_factory() as session:
        session.delete(session.get(Story, story_id))
        session.commit()

    with session_factory() as session:
        assert session.get(ContinuitySnapshot, snapshot_id) is None


def test_deleting_scene_cascades_to_continuity_snapshot(session_factory, story_id, scene_id):
    with session_factory() as session:
        snapshot = ContinuitySnapshot(
            story_id=story_id, through_scene_id=scene_id, narrative_state="Mara is at the station."
        )
        session.add(snapshot)
        session.commit()
        snapshot_id = snapshot.id

    with session_factory() as session:
        session.delete(session.get(Scene, scene_id))
        session.commit()

    with session_factory() as session:
        assert session.get(ContinuitySnapshot, snapshot_id) is None
