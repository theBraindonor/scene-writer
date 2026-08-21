import pytest

import scene.data.database as database_module
from scene.core.story import create_story, get_story
from scene.data.database import session_scope
from scene.gui.entity_column.story_detail import StoryDetailWidget


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_story():
    with session_scope() as session:
        story = create_story(session, title="A Story", scenario="A scenario", style_guidance="Terse")
        return story.id


def test_load_populates_fields(qtbot):
    story_id = seed_story()

    widget = StoryDetailWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)

    assert widget.title_edit.text() == "A Story"
    assert widget.scenario_edit.toPlainText() == "A scenario"
    assert widget.style_guidance_edit.toPlainText() == "Terse"
    assert widget.archive_button.text() == "Archive"


def test_save_persists_edited_fields(qtbot):
    story_id = seed_story()

    widget = StoryDetailWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)

    widget.title_edit.setText("New Title")
    widget.scenario_edit.setPlainText("New scenario")
    widget.style_guidance_edit.setPlainText("New style")
    widget.save_button.click()

    with session_scope() as session:
        story = get_story(session, story_id)
        assert story.title == "New Title"
        assert story.scenario == "New scenario"
        assert story.style_guidance == "New style"


def test_archive_then_unarchive_toggles_and_persists(qtbot):
    story_id = seed_story()

    widget = StoryDetailWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)

    widget.archive_button.click()
    with session_scope() as session:
        assert get_story(session, story_id).is_archived == 1
    assert widget.archive_button.text() == "Unarchive"

    widget.archive_button.click()
    with session_scope() as session:
        assert get_story(session, story_id).is_archived == 0
    assert widget.archive_button.text() == "Archive"
