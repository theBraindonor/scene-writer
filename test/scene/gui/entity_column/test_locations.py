import pytest

import scene.data.database as database_module
from scene.core.location import create_location, list_locations
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.entity_column.locations import LocationsWidget


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_story():
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A story brief")
        return story.id


def test_load_lists_existing_locations(qtbot):
    story_id = seed_story()
    with session_scope() as session:
        create_location(session, story_id=story_id, name="The Tavern")

    widget = LocationsWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)

    assert widget.list_widget.count() == 1
    assert widget.list_widget.item(0).text() == "The Tavern"


def test_new_location_adds_and_selects(qtbot):
    story_id = seed_story()

    widget = LocationsWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)

    widget.new_button.click()

    assert widget.list_widget.count() == 1
    assert widget.name_edit.text() == "New Location"
    with session_scope() as session:
        assert len(list_locations(session, story_id)) == 1


def test_save_persists_edited_fields(qtbot):
    story_id = seed_story()

    widget = LocationsWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()

    widget.name_edit.setText("The Tavern")
    widget.description_edit.setPlainText("A dim, crowded room.")
    widget.save_button.click()

    with session_scope() as session:
        locations = list_locations(session, story_id)
        assert len(locations) == 1
        assert locations[0].name == "The Tavern"
        assert locations[0].description == "A dim, crowded room."
    assert widget.list_widget.item(0).text() == "The Tavern"


def test_delete_confirmed_removes_location(qtbot, monkeypatch):
    story_id = seed_story()

    widget = LocationsWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()

    monkeypatch.setattr(widget, "_confirm_delete", lambda name: True)
    widget.delete_button.click()

    assert widget.list_widget.count() == 0
    with session_scope() as session:
        assert list_locations(session, story_id) == []


def test_delete_declined_keeps_location(qtbot, monkeypatch):
    story_id = seed_story()

    widget = LocationsWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()

    monkeypatch.setattr(widget, "_confirm_delete", lambda name: False)
    widget.delete_button.click()

    assert widget.list_widget.count() == 1
    with session_scope() as session:
        assert len(list_locations(session, story_id)) == 1


def test_locations_changed_emitted_on_refresh(qtbot):
    story_id = seed_story()

    widget = LocationsWidget()
    qtbot.addWidget(widget)

    with qtbot.waitSignal(widget.locations_changed, timeout=1000):
        widget.load(story_id)
