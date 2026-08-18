import pytest
from sqlalchemy.exc import IntegrityError

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


def test_create_story(session_factory):
    with session_factory() as session:
        story = Story(title="A Title", scenario="A scenario")
        session.add(story)
        session.commit()

        assert story.id is not None
        assert story.is_archived == 0


def test_title_must_not_be_blank(session_factory):
    with session_factory() as session:
        session.add(Story(title="   ", scenario="A scenario"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_scenario_must_not_be_blank(session_factory):
    with session_factory() as session:
        session.add(Story(title="A Title", scenario=""))
        with pytest.raises(IntegrityError):
            session.commit()


def test_is_archived_must_be_boolean(session_factory):
    with session_factory() as session:
        session.add(Story(title="A Title", scenario="A scenario", is_archived=2))
        with pytest.raises(IntegrityError):
            session.commit()
