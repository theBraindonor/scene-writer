import pytest
from PySide6.QtCore import Qt

import scene.data.database as database_module
from scene.core.character import create_character
from scene.core.location import create_location
from scene.core.scene import list_scenes
from scene.core.scene_character import list_characters_for_scene
from scene.core.scene_location import list_locations_for_scene
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.entity_column.scenes import ScenesWidget


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_story():
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A story brief")
        return story.id


def test_new_scene_adds_and_selects(qtbot):
    story_id = seed_story()

    widget = ScenesWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)

    widget.new_button.click()

    assert widget.list_widget.count() == 1
    assert widget.brief_edit.toPlainText() == "New scene"
    with session_scope() as session:
        scenes = list_scenes(session, story_id)
        assert len(scenes) == 1
        assert scenes[0].position == 0


def test_second_new_scene_gets_next_position(qtbot):
    story_id = seed_story()

    widget = ScenesWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)

    widget.new_button.click()
    widget.new_button.click()

    with session_scope() as session:
        scenes = list_scenes(session, story_id)
        assert [scene.position for scene in scenes] == [0, 1]


def test_save_persists_edited_fields(qtbot):
    story_id = seed_story()

    widget = ScenesWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()

    widget.heading_edit.setText("Arrival")
    widget.brief_edit.setPlainText("They arrive at the gate.")
    widget.required_actions_edit.setPlainText("Knock on the door.")
    widget.desired_outcome_edit.setPlainText("They find the map.")
    widget.target_length_edit.setText("Short")
    widget.position_edit.setValue(0)
    widget.save_button.click()

    with session_scope() as session:
        scenes = list_scenes(session, story_id)
        assert len(scenes) == 1
        assert scenes[0].heading == "Arrival"
        assert scenes[0].brief == "They arrive at the gate."
        assert scenes[0].required_actions == "Knock on the door."
        assert scenes[0].desired_outcome == "They find the map."
        assert scenes[0].target_length == "Short"


def test_pov_character_combo_populated_and_saved(qtbot):
    story_id = seed_story()
    with session_scope() as session:
        character = create_character(session, story_id=story_id, name="Alex")
        character_id = character.id

    widget = ScenesWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()

    assert widget.pov_character_combo.count() == 2
    assert widget.pov_character_combo.currentData() is None

    index = widget.pov_character_combo.findData(character_id)
    widget.pov_character_combo.setCurrentIndex(index)
    widget.save_button.click()

    with session_scope() as session:
        scenes = list_scenes(session, story_id)
        assert scenes[0].pov_character_id == character_id


def test_pov_character_combo_reselects_none_after_reload(qtbot):
    story_id = seed_story()
    with session_scope() as session:
        create_character(session, story_id=story_id, name="Alex")

    widget = ScenesWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()

    widget.save_button.click()

    assert widget.pov_character_combo.currentIndex() == 0
    assert widget.pov_character_combo.currentData() is None


def test_delete_confirmed_removes_scene(qtbot, monkeypatch):
    story_id = seed_story()

    widget = ScenesWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()

    monkeypatch.setattr(widget, "_confirm_delete", lambda label: True)
    widget.delete_button.click()

    assert widget.list_widget.count() == 0
    with session_scope() as session:
        assert list_scenes(session, story_id) == []


def test_selecting_scene_emits_scene_selected(qtbot):
    story_id = seed_story()

    widget = ScenesWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)

    with session_scope() as session:
        from scene.core.scene import create_scene

        scene = create_scene(session, story_id=story_id, position=0, brief="Opening")
        scene_id = scene.id
    widget.refresh()

    with qtbot.waitSignal(widget.scene_selected, timeout=1000) as blocker:
        widget.list_widget.setCurrentRow(0)
    assert blocker.args == [scene_id]


def test_checking_character_assigns_and_unchecking_unassigns(qtbot):
    story_id = seed_story()
    with session_scope() as session:
        character = create_character(session, story_id=story_id, name="Alex")
        character_id = character.id

    widget = ScenesWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()
    scene_id = widget.current_scene_id

    assert widget.character_list.count() == 1
    item = widget.character_list.item(0)
    assert item.checkState() == Qt.CheckState.Unchecked

    item.setCheckState(Qt.CheckState.Checked)
    with session_scope() as session:
        assigned = {character.id for character in list_characters_for_scene(session, scene_id)}
        assert assigned == {character_id}

    item.setCheckState(Qt.CheckState.Unchecked)
    with session_scope() as session:
        assigned = {character.id for character in list_characters_for_scene(session, scene_id)}
        assert assigned == set()


def test_checking_location_assigns_and_unchecking_unassigns(qtbot):
    story_id = seed_story()
    with session_scope() as session:
        location = create_location(session, story_id=story_id, name="The Tavern")
        location_id = location.id

    widget = ScenesWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()
    scene_id = widget.current_scene_id

    assert widget.location_list.count() == 1
    item = widget.location_list.item(0)
    item.setCheckState(Qt.CheckState.Checked)
    with session_scope() as session:
        assigned = {location.id for location in list_locations_for_scene(session, scene_id)}
        assert assigned == {location_id}

    item.setCheckState(Qt.CheckState.Unchecked)
    with session_scope() as session:
        assigned = {location.id for location in list_locations_for_scene(session, scene_id)}
        assert assigned == set()


def test_refresh_assignment_options_reflects_newly_created_character(qtbot):
    story_id = seed_story()

    widget = ScenesWidget()
    qtbot.addWidget(widget)
    widget.load(story_id)
    widget.new_button.click()

    assert widget.character_list.count() == 0

    with session_scope() as session:
        create_character(session, story_id=story_id, name="Alex")
    widget.refresh_assignment_options()

    assert widget.character_list.count() == 1
    assert widget.character_list.item(0).text() == "Alex"
