import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

import scene.data.database as database_module
from scene.core.rendering import create_rendering, set_active_rendering
from scene.core.scene import create_scene
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.main_window import MainWindow
from scene.gui.rendering_column import NO_SCENE_SELECTED_TEXT


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
    assert "Chat Panel" in labels
    assert window.entity_column.stack.currentWidget() is window.entity_column.empty_label
    assert window.rendering_column.stack.currentWidget() is window.rendering_column.no_selection_label
    assert window.rendering_column.no_selection_label.text() == NO_SCENE_SELECTED_TEXT


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


def test_selecting_scene_updates_rendering_column(qtbot):
    story_id = seed_story("A Story")
    with session_scope() as session:
        scene = create_scene(session, story_id=story_id, position=0, description="Opening")
        rendering = create_rendering(session, scene_id=scene.id, body="Once upon a time.")
        set_active_rendering(session, rendering.id)

    window = make_window(qtbot)
    window.sidebar.story_list.setCurrentRow(0)

    with qtbot.waitSignal(window.entity_column.current_scene_changed, timeout=1000):
        window.entity_column.scenes.list_widget.setCurrentRow(0)

    assert window.rendering_column.stack.currentWidget() is window.rendering_column.body_view
    assert window.rendering_column.body_view.toPlainText() == "Once upon a time."


def test_switching_story_resets_rendering_column(qtbot):
    first_story_id = seed_story("First Story")
    seed_story("Second Story")
    with session_scope() as session:
        scene = create_scene(session, story_id=first_story_id, position=0, description="Opening")
        rendering = create_rendering(session, scene_id=scene.id, body="Once upon a time.")
        set_active_rendering(session, rendering.id)

    window = make_window(qtbot)
    window.sidebar.story_list.setCurrentRow(0)
    window.entity_column.scenes.list_widget.setCurrentRow(0)
    assert window.rendering_column.stack.currentWidget() is window.rendering_column.body_view

    window.sidebar.story_list.setCurrentRow(1)

    assert window.rendering_column.stack.currentWidget() is window.rendering_column.no_selection_label


def test_collapse_toggle_drives_sidebar_pane_width_to_zero_and_back(qtbot):
    window = make_window(qtbot)

    initial_width = window.splitter.sizes()[0]
    assert initial_width > 0

    qtbot.mouseClick(window.sidebar.collapse_button, Qt.MouseButton.LeftButton)
    assert window.splitter.sizes()[0] == 0

    qtbot.mouseClick(window.sidebar.collapse_button, Qt.MouseButton.LeftButton)
    assert window.splitter.sizes()[0] > 0
