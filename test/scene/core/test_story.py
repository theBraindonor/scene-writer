import pytest

from scene.core.story import (
    archive_story,
    create_story,
    get_story,
    list_stories,
    unarchive_story,
    update_story,
)
from scene.data.database import get_engine, get_session_factory, init_db


@pytest.fixture
def session():
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    factory = get_session_factory(engine)
    try:
        with factory() as session:
            yield session
    finally:
        engine.dispose()


def test_create_and_get_story(session):
    story = create_story(session, title="Title", story_brief="Story brief")

    fetched = get_story(session, story.id)

    assert fetched is not None
    assert fetched.title == "Title"
    assert fetched.generation_guideance is None


def test_create_story_with_generation_guideance(session):
    story = create_story(session, title="Title", story_brief="Story brief", generation_guideance="No profanity")

    assert story.generation_guideance == "No profanity"


def test_get_missing_story_returns_none(session):
    assert get_story(session, 999) is None


def test_list_stories_excludes_archived_by_default(session):
    active = create_story(session, title="Active", story_brief="Story brief")
    archived = create_story(session, title="Archived", story_brief="Story brief")
    archive_story(session, archived.id)

    stories = list_stories(session)

    assert [story.id for story in stories] == [active.id]


def test_list_stories_include_archived(session):
    active = create_story(session, title="Active", story_brief="Story brief")
    archived = create_story(session, title="Archived", story_brief="Story brief")
    archive_story(session, archived.id)

    stories = list_stories(session, include_archived=True)

    assert {story.id for story in stories} == {active.id, archived.id}


def test_update_story(session):
    story = create_story(session, title="Title", story_brief="Story brief")

    updated = update_story(session, story.id, title="New Title")

    assert updated.title == "New Title"
    assert updated.story_brief == "Story brief"


def test_update_story_brief_and_style_guidance(session):
    story = create_story(session, title="Title", story_brief="Story brief")

    updated = update_story(session, story.id, story_brief="New brief", style_guidance="New Style")

    assert updated.title == "Title"
    assert updated.story_brief == "New brief"
    assert updated.style_guidance == "New Style"


def test_update_story_generation_guideance(session):
    story = create_story(session, title="Title", story_brief="Story brief")

    updated = update_story(session, story.id, generation_guideance="No profanity")

    assert updated.generation_guideance == "No profanity"


def test_update_missing_story_returns_none(session):
    assert update_story(session, 999, title="New Title") is None


def test_archive_and_unarchive_story(session):
    story = create_story(session, title="Title", story_brief="Story brief")

    archived = archive_story(session, story.id)
    assert archived.is_archived == 1

    unarchived = unarchive_story(session, story.id)
    assert unarchived.is_archived == 0


def test_archive_missing_story_returns_none(session):
    assert archive_story(session, 999) is None
