import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

import scene.data.database as database_module
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.main_window import MainWindow


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_story(title="A Story"):
    with session_scope() as session:
        story = create_story(session, title=title, scenario="A scenario")
        return story.id


def make_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(900, 600)
    window.show()
    return window


def test_window_shows_placeholder_panes(qtbot):
    window = make_window(qtbot)

    labels = {label.text() for label in window.findChildren(QLabel)}
    assert "Rendering Column" in labels
    assert "Chat Panel" in labels
    assert window.entity_column.stack.currentWidget() is window.entity_column.empty_label


def test_selecting_story_updates_current_story_id_and_emits_signal(qtbot):
    story_id = seed_story("A Story")
    window = make_window(qtbot)

    with qtbot.waitSignal(window.current_story_changed, timeout=1000) as blocker:
        window.sidebar.story_list.setCurrentRow(0)

    assert blocker.args == [story_id]
    assert window.current_story_id == story_id
    assert window.entity_column.current_story_id == story_id


def test_creating_story_via_sidebar_updates_window(qtbot, monkeypatch):
    window = make_window(qtbot)

    monkeypatch.setattr(window.sidebar, "_prompt_new_story", lambda: ("New Story", "A scenario", None))

    with qtbot.waitSignal(window.current_story_changed, timeout=1000) as blocker:
        qtbot.mouseClick(window.sidebar.new_story_button, Qt.MouseButton.LeftButton)

    assert window.current_story_id == blocker.args[0]
    assert window.sidebar.story_list.currentItem().text() == "New Story"


def test_collapse_toggle_drives_sidebar_pane_width_to_zero_and_back(qtbot):
    window = make_window(qtbot)

    initial_width = window.splitter.sizes()[0]
    assert initial_width > 0

    qtbot.mouseClick(window.sidebar.collapse_button, Qt.MouseButton.LeftButton)
    assert window.splitter.sizes()[0] == 0

    qtbot.mouseClick(window.sidebar.collapse_button, Qt.MouseButton.LeftButton)
    assert window.splitter.sizes()[0] > 0
