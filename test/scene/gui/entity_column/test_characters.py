import pytest

import scene.data.database as database_module
from scene.core.character import list_characters
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.entity_column.characters import CharactersWidget


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_story():
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A story brief")
        return story.id


def test_load_lists_existing_characters(qtbot):
    story_id = seed_story()
    with session_scope() as session:
        from scene.core.character import create_character

        create_character(session, story_id=story_id, name="Alex")

    widget = CharactersWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)

    assert widget.list_widget.count() == 1
    assert widget.list_widget.item(0).text() == "Alex"


def test_new_character_adds_and_selects(qtbot):
    story_id = seed_story()

    widget = CharactersWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)

    widget.new_button.click()

    assert widget.list_widget.count() == 1
    assert widget.name_edit.text() == "New Character"
    with session_scope() as session:
        assert len(list_characters(session, story_id)) == 1


def test_save_persists_edited_fields(qtbot):
    story_id = seed_story()

    widget = CharactersWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()

    widget.name_edit.setText("Alex")
    widget.description_edit.setPlainText("A wanderer")
    widget.motive_edit.setPlainText("Revenge")
    widget.save_button.click()

    with session_scope() as session:
        characters = list_characters(session, story_id)
        assert len(characters) == 1
        assert characters[0].name == "Alex"
        assert characters[0].description == "A wanderer"
        assert characters[0].motive == "Revenge"
    assert widget.list_widget.item(0).text() == "Alex"


def test_delete_confirmed_removes_character(qtbot, monkeypatch):
    story_id = seed_story()

    widget = CharactersWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()

    monkeypatch.setattr(widget, "_confirm_delete", lambda name: True)
    widget.delete_button.click()

    assert widget.list_widget.count() == 0
    with session_scope() as session:
        assert list_characters(session, story_id) == []


def test_delete_declined_keeps_character(qtbot, monkeypatch):
    story_id = seed_story()

    widget = CharactersWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()

    monkeypatch.setattr(widget, "_confirm_delete", lambda name: False)
    widget.delete_button.click()

    assert widget.list_widget.count() == 1
    with session_scope() as session:
        assert len(list_characters(session, story_id)) == 1


def test_characters_changed_emitted_on_refresh(qtbot):
    story_id = seed_story()

    widget = CharactersWidget()
    qtbot.addWidget(widget)

    with qtbot.waitSignal(widget.characters_changed, timeout=1000):
        widget.load(story_id)
