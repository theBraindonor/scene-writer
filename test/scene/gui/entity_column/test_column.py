import pytest

import scene.data.database as database_module
from scene.core.scene import create_scene
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.entity_column.column import EntityColumn


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_story(title="A Story"):
    with session_scope() as session:
        story = create_story(session, title=title, story_brief="A story brief")
        return story.id


def test_shows_empty_state_by_default(qtbot):
    widget = EntityColumn()
    qtbot.addWidget(widget)

    assert widget.stack.currentWidget() is widget.empty_label


def test_set_story_shows_content_and_loads_sections(qtbot):
    story_id = seed_story()

    widget = EntityColumn()
    qtbot.addWidget(widget)
    widget.set_story(story_id)

    assert widget.stack.currentWidget() is widget.tabs
    assert widget.story_detail.story_id == story_id
    assert widget.scenes.story_id == story_id
    assert widget.characters.story_id == story_id
    assert widget.locations.story_id == story_id


def test_tabs_have_expected_labels_and_order(qtbot):
    widget = EntityColumn()
    qtbot.addWidget(widget)

    labels = [widget.tabs.tabText(i) for i in range(widget.tabs.count())]
    assert labels == ["Story", "Characters", "Locations", "Scenes"]


def test_set_story_none_shows_empty_state_and_resets_scene(qtbot):
    story_id = seed_story()

    widget = EntityColumn()
    qtbot.addWidget(widget)
    widget.set_story(story_id)
    widget.scenes.new_button.click()
    assert widget.current_scene_id is not None

    with qtbot.waitSignal(widget.current_scene_changed, timeout=1000) as blocker:
        widget.set_story(None)
    assert blocker.args == [None]
    assert widget.current_scene_id is None
    assert widget.stack.currentWidget() is widget.empty_label


def test_selecting_scene_updates_current_scene_id_and_emits_signal(qtbot):
    story_id = seed_story()

    widget = EntityColumn()
    qtbot.addWidget(widget)
    widget.set_story(story_id)

    with qtbot.waitSignal(widget.current_scene_changed, timeout=1000) as blocker:
        widget.scenes.new_button.click()

    assert widget.current_scene_id is not None
    assert blocker.args == [widget.current_scene_id]


def test_switching_story_resets_current_scene(qtbot):
    first_story_id = seed_story("First Story")
    second_story_id = seed_story("Second Story")

    widget = EntityColumn()
    qtbot.addWidget(widget)
    widget.set_story(first_story_id)
    widget.scenes.new_button.click()
    assert widget.current_scene_id is not None

    widget.set_story(second_story_id)

    assert widget.current_scene_id is None


def test_show_story_tab_switches_to_story_tab(qtbot):
    story_id = seed_story()
    widget = EntityColumn()
    qtbot.addWidget(widget)
    widget.set_story(story_id)
    widget.tabs.setCurrentIndex(widget._SCENES_TAB_INDEX)

    widget.show_story_tab()

    assert widget.tabs.currentIndex() == widget._STORY_TAB_INDEX


def test_show_characters_tab_switches_tab_and_selects_character(qtbot):
    story_id = seed_story()
    widget = EntityColumn()
    qtbot.addWidget(widget)
    widget.set_story(story_id)
    widget.characters.new_button.click()
    character_id = widget.characters.current_character_id

    widget.tabs.setCurrentIndex(widget._STORY_TAB_INDEX)
    widget.show_characters_tab(character_id)

    assert widget.tabs.currentIndex() == widget._CHARACTERS_TAB_INDEX
    assert widget.characters.current_character_id == character_id


def test_show_locations_tab_switches_tab_and_selects_location(qtbot):
    story_id = seed_story()
    widget = EntityColumn()
    qtbot.addWidget(widget)
    widget.set_story(story_id)
    widget.locations.new_button.click()
    location_id = widget.locations.current_location_id

    widget.tabs.setCurrentIndex(widget._STORY_TAB_INDEX)
    widget.show_locations_tab(location_id)

    assert widget.tabs.currentIndex() == widget._LOCATIONS_TAB_INDEX
    assert widget.locations.current_location_id == location_id


def test_show_scenes_tab_switches_to_scenes_tab(qtbot):
    story_id = seed_story()
    widget = EntityColumn()
    qtbot.addWidget(widget)
    widget.set_story(story_id)
    widget.tabs.setCurrentIndex(widget._STORY_TAB_INDEX)

    widget.show_scenes_tab()

    assert widget.tabs.currentIndex() == widget._SCENES_TAB_INDEX


def test_refresh_scene_selection_selects_the_given_scene_without_switching_tabs(qtbot):
    story_id = seed_story()
    with session_scope() as session:
        scene = create_scene(session, story_id=story_id, position=0, brief="A scene")
        scene_id = scene.id

    widget = EntityColumn()
    qtbot.addWidget(widget)
    widget.set_story(story_id)
    widget.tabs.setCurrentIndex(widget._STORY_TAB_INDEX)

    widget.refresh_scene_selection(scene_id)

    assert widget.tabs.currentIndex() == widget._STORY_TAB_INDEX
    assert widget.current_scene_id == scene_id
    assert widget.scenes.current_scene_id == scene_id


def test_refresh_scene_selection_with_none_clears_selection(qtbot):
    story_id = seed_story()
    widget = EntityColumn()
    qtbot.addWidget(widget)
    widget.set_story(story_id)
    widget.scenes.new_button.click()
    assert widget.current_scene_id is not None

    widget.refresh_scene_selection(None)

    assert widget.current_scene_id is None
