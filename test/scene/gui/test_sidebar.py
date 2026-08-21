import pytest
from PySide6.QtCore import Qt

import scene.data.database as database_module
from scene.core.story import create_story, list_stories
from scene.data.database import session_scope
from scene.gui.sidebar import Sidebar


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_story(title="A Story"):
    with session_scope() as session:
        story = create_story(session, title=title, scenario="A scenario")
        return story.id


def test_story_list_reflects_database(qtbot):
    story_id = seed_story("A Story")

    sidebar = Sidebar()
    qtbot.addWidget(sidebar)

    assert sidebar.story_list.count() == 1
    item = sidebar.story_list.item(0)
    assert item.text() == "A Story"
    assert item.data(Qt.ItemDataRole.UserRole) == story_id


def test_selecting_story_emits_signal(qtbot):
    story_id = seed_story("A Story")

    sidebar = Sidebar()
    qtbot.addWidget(sidebar)

    with qtbot.waitSignal(sidebar.story_selected, timeout=1000) as blocker:
        sidebar.story_list.setCurrentRow(0)
    assert blocker.args == [story_id]


def test_creating_story_adds_and_selects(qtbot, monkeypatch):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    assert sidebar.story_list.count() == 0

    monkeypatch.setattr(sidebar, "_prompt_new_story", lambda: ("New Story", "A scenario", None))

    with qtbot.waitSignal(sidebar.story_selected, timeout=1000) as blocker:
        qtbot.mouseClick(sidebar.new_story_button, Qt.MouseButton.LeftButton)

    assert sidebar.story_list.count() == 1
    assert sidebar.story_list.item(0).text() == "New Story"
    assert sidebar.story_list.currentItem().text() == "New Story"

    with session_scope() as session:
        stories = list_stories(session)
        assert len(stories) == 1
        assert stories[0].id == blocker.args[0]


def test_new_story_declined_does_not_change_list(qtbot, monkeypatch):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)

    monkeypatch.setattr(sidebar, "_prompt_new_story", lambda: None)

    qtbot.mouseClick(sidebar.new_story_button, Qt.MouseButton.LeftButton)

    assert sidebar.story_list.count() == 0


def test_collapse_toggle_emits_signal_and_updates_label(qtbot):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)

    assert sidebar.collapse_button.text() == "Collapse"

    with qtbot.waitSignal(sidebar.collapse_toggled, timeout=1000) as blocker:
        sidebar.collapse_button.setChecked(True)
    assert blocker.args == [True]
    assert sidebar.collapse_button.text() == "Expand"

    with qtbot.waitSignal(sidebar.collapse_toggled, timeout=1000) as blocker:
        sidebar.collapse_button.setChecked(False)
    assert blocker.args == [False]
    assert sidebar.collapse_button.text() == "Collapse"
