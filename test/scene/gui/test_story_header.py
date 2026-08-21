import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

import scene.data.database as database_module
from scene.core.story import archive_story, create_story, list_stories
from scene.data.database import session_scope
from scene.gui.story_header import NO_STORY_SELECTED_TEXT, StoryHeader, StoryPickerDialog


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_story(title="A Story"):
    with session_scope() as session:
        story = create_story(session, title=title, scenario="A scenario")
        return story.id


def test_label_shows_no_story_selected_by_default(qtbot):
    header = StoryHeader()
    qtbot.addWidget(header)

    assert header.story_label.text() == NO_STORY_SELECTED_TEXT


def test_set_current_story_updates_label_without_emitting_signal(qtbot):
    story_id = seed_story("A Story")

    header = StoryHeader()
    qtbot.addWidget(header)

    with qtbot.assertNotEmitted(header.story_selected):
        header.set_current_story(story_id)
    assert header.story_label.text() == "A Story"


def test_set_current_story_none_resets_label(qtbot):
    story_id = seed_story("A Story")

    header = StoryHeader()
    qtbot.addWidget(header)
    header.set_current_story(story_id)

    header.set_current_story(None)

    assert header.story_label.text() == NO_STORY_SELECTED_TEXT


def test_new_story_creates_and_selects(qtbot, monkeypatch):
    header = StoryHeader()
    qtbot.addWidget(header)

    monkeypatch.setattr(header, "_prompt_new_story", lambda: ("New Story", "A scenario", None))

    with qtbot.waitSignal(header.story_selected, timeout=1000) as blocker:
        qtbot.mouseClick(header.new_story_button, Qt.MouseButton.LeftButton)

    with session_scope() as session:
        stories = list_stories(session)
        assert len(stories) == 1
        assert stories[0].id == blocker.args[0]


def test_new_story_declined_creates_nothing(qtbot, monkeypatch):
    header = StoryHeader()
    qtbot.addWidget(header)

    monkeypatch.setattr(header, "_prompt_new_story", lambda: None)

    with qtbot.assertNotEmitted(header.story_selected):
        qtbot.mouseClick(header.new_story_button, Qt.MouseButton.LeftButton)

    with session_scope() as session:
        assert list_stories(session) == []
    assert header.story_label.text() == NO_STORY_SELECTED_TEXT


def test_open_with_selection_emits_signal(qtbot, monkeypatch):
    story_id = seed_story("A Story")

    header = StoryHeader()
    qtbot.addWidget(header)

    monkeypatch.setattr(header, "_prompt_story_picker", lambda: story_id)

    with qtbot.waitSignal(header.story_selected, timeout=1000) as blocker:
        qtbot.mouseClick(header.open_button, Qt.MouseButton.LeftButton)

    assert blocker.args == [story_id]


def test_open_cancelled_emits_nothing(qtbot, monkeypatch):
    header = StoryHeader()
    qtbot.addWidget(header)

    monkeypatch.setattr(header, "_prompt_story_picker", lambda: None)

    with qtbot.assertNotEmitted(header.story_selected):
        qtbot.mouseClick(header.open_button, Qt.MouseButton.LeftButton)


def test_picker_excludes_archived_by_default(qtbot):
    active_id = seed_story("Active Story")
    archived_id = seed_story("Archived Story")
    with session_scope() as session:
        archive_story(session, archived_id)

    dialog = StoryPickerDialog()
    qtbot.addWidget(dialog)

    titles = [dialog.list_widget.item(i).text() for i in range(dialog.list_widget.count())]
    assert titles == ["Active Story"]
    ids = [dialog.list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(dialog.list_widget.count())]
    assert ids == [active_id]


def test_picker_include_archived_checkbox_toggles_list(qtbot):
    seed_story("Active Story")
    archived_id = seed_story("Archived Story")
    with session_scope() as session:
        archive_story(session, archived_id)

    dialog = StoryPickerDialog()
    qtbot.addWidget(dialog)

    dialog.include_archived_checkbox.setChecked(True)
    titles = {dialog.list_widget.item(i).text() for i in range(dialog.list_widget.count())}
    assert titles == {"Active Story", "Archived Story"}

    dialog.include_archived_checkbox.setChecked(False)
    titles = {dialog.list_widget.item(i).text() for i in range(dialog.list_widget.count())}
    assert titles == {"Active Story"}


def test_picker_ok_button_enabled_state_tracks_selection(qtbot):
    seed_story("A Story")

    dialog = StoryPickerDialog()
    qtbot.addWidget(dialog)
    ok_button = dialog.button_box.button(dialog.button_box.StandardButton.Ok)

    assert not ok_button.isEnabled()

    dialog.list_widget.setCurrentRow(0)
    assert ok_button.isEnabled()


def test_picker_selected_story_id_returns_current_item(qtbot):
    story_id = seed_story("A Story")

    dialog = StoryPickerDialog()
    qtbot.addWidget(dialog)

    assert dialog.selected_story_id() is None

    dialog.list_widget.setCurrentRow(0)
    assert dialog.selected_story_id() == story_id


def test_picker_double_clicking_a_row_accepts_the_dialog(qtbot):
    seed_story("A Story")

    dialog = StoryPickerDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    accepted = []
    dialog.accepted.connect(lambda: accepted.append(True))

    dialog.list_widget.itemDoubleClicked.emit(dialog.list_widget.item(0))

    assert accepted == [True]
    assert dialog.result() == QDialog.DialogCode.Accepted
