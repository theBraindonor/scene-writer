import pytest
import yaml

import scene.data.database as database_module
from scene.core.character import create_character
from scene.core.location import create_location
from scene.core.scene import create_scene
from scene.core.scene_character import assign_character
from scene.core.scene_location import assign_location
from scene.core.story import archive_story, create_story
from scene.data.database import session_scope
from scene.gui.story_export import build_story_export_data
from scene.gui.story_import import (
    DuplicateStoryTitleDialog,
    import_story,
    parse_story_import_file,
    story_title_exists,
)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


VALID_DATA = {
    "story": {
        "title": "A Story",
        "story_brief": "A brief",
        "style_guidance": None,
        "generation_guideance": None,
        "is_archived": False,
    },
    "characters": [{"name": "Alex", "description": "Hero", "motive": "Justice"}],
    "locations": [{"name": "The Keep", "description": "An old fortress"}],
    "scenes": [
        {
            "position": 0,
            "heading": "Chapter One",
            "brief": "Opening",
            "required_actions": None,
            "desired_outcome": None,
            "target_length": None,
            "pov_character": "Alex",
            "characters": ["Alex"],
            "locations": ["The Keep"],
        }
    ],
}


def write_yaml(tmp_path, data, name="story.yaml"):
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def test_parse_story_import_file_parses_a_well_formed_file(tmp_path):
    path = write_yaml(tmp_path, VALID_DATA)

    data = parse_story_import_file(path)

    assert data == VALID_DATA


def test_parse_story_import_file_round_trips_a_real_export(tmp_path):
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A brief")
        character = create_character(session, story_id=story.id, name="Alex")
        location = create_location(session, story_id=story.id, name="The Keep")
        scene = create_scene(session, story_id=story.id, position=0, brief="Opening", pov_character_id=character.id)
        assign_character(session, scene.id, character.id)
        assign_location(session, scene.id, location.id)
        story_id = story.id

    with session_scope() as session:
        exported = build_story_export_data(session, story_id)
    path = write_yaml(tmp_path, exported)

    data = parse_story_import_file(path)

    assert data == exported


def test_parse_story_import_file_raises_for_missing_file(tmp_path):
    with pytest.raises(ValueError, match="Could not read the file"):
        parse_story_import_file(str(tmp_path / "missing.yaml"))


def test_parse_story_import_file_raises_for_invalid_yaml(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("story: [unterminated", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid YAML"):
        parse_story_import_file(str(path))


def test_parse_story_import_file_raises_for_malformed_scenes_list(tmp_path):
    data = yaml.safe_load(yaml.safe_dump(VALID_DATA))
    data["scenes"] = "not a list"
    path = write_yaml(tmp_path, data)

    with pytest.raises(ValueError, match="are malformed"):
        parse_story_import_file(path)


def test_parse_story_import_file_raises_for_non_mapping_document(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not contain a story export"):
        parse_story_import_file(str(path))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data["story"].update(title=""),
        lambda data: data["story"].update(story_brief=""),
        lambda data: data["story"].pop("title"),
    ],
)
def test_parse_story_import_file_raises_for_missing_title_or_brief(tmp_path, mutate):
    data = yaml.safe_load(yaml.safe_dump(VALID_DATA))
    mutate(data)
    path = write_yaml(tmp_path, data)

    with pytest.raises(ValueError, match="missing a story title or story brief"):
        parse_story_import_file(path)


def test_parse_story_import_file_raises_for_scene_missing_brief(tmp_path):
    data = yaml.safe_load(yaml.safe_dump(VALID_DATA))
    data["scenes"][0]["brief"] = ""
    path = write_yaml(tmp_path, data)

    with pytest.raises(ValueError, match="missing its brief"):
        parse_story_import_file(path)


def test_parse_story_import_file_raises_for_unknown_pov_character(tmp_path):
    data = yaml.safe_load(yaml.safe_dump(VALID_DATA))
    data["scenes"][0]["pov_character"] = "Nobody"
    path = write_yaml(tmp_path, data)

    with pytest.raises(ValueError, match="unknown POV character"):
        parse_story_import_file(path)


def test_parse_story_import_file_raises_for_unknown_assigned_character(tmp_path):
    data = yaml.safe_load(yaml.safe_dump(VALID_DATA))
    data["scenes"][0]["characters"] = ["Nobody"]
    path = write_yaml(tmp_path, data)

    with pytest.raises(ValueError, match="unknown character"):
        parse_story_import_file(path)


def test_parse_story_import_file_raises_for_unknown_assigned_location(tmp_path):
    data = yaml.safe_load(yaml.safe_dump(VALID_DATA))
    data["scenes"][0]["locations"] = ["Nowhere"]
    path = write_yaml(tmp_path, data)

    with pytest.raises(ValueError, match="unknown location"):
        parse_story_import_file(path)


def test_parse_story_import_file_raises_for_character_missing_name(tmp_path):
    data = yaml.safe_load(yaml.safe_dump(VALID_DATA))
    data["characters"][0].pop("name")
    path = write_yaml(tmp_path, data)

    with pytest.raises(ValueError, match="character in the file is missing its name"):
        parse_story_import_file(path)


def test_parse_story_import_file_raises_for_location_missing_name(tmp_path):
    data = yaml.safe_load(yaml.safe_dump(VALID_DATA))
    data["locations"][0].pop("name")
    path = write_yaml(tmp_path, data)

    with pytest.raises(ValueError, match="location in the file is missing its name"):
        parse_story_import_file(path)


def test_parse_story_import_file_raises_for_duplicate_character_name(tmp_path):
    data = yaml.safe_load(yaml.safe_dump(VALID_DATA))
    data["characters"].append({"name": "Alex", "description": None, "motive": None})
    path = write_yaml(tmp_path, data)

    with pytest.raises(ValueError, match="more than once"):
        parse_story_import_file(path)


def test_parse_story_import_file_raises_for_duplicate_location_name(tmp_path):
    data = yaml.safe_load(yaml.safe_dump(VALID_DATA))
    data["locations"].append({"name": "The Keep", "description": None})
    path = write_yaml(tmp_path, data)

    with pytest.raises(ValueError, match="more than once"):
        parse_story_import_file(path)


def test_story_title_exists_true_for_active_story():
    with session_scope() as session:
        create_story(session, title="A Story", story_brief="A brief")

    with session_scope() as session:
        assert story_title_exists(session, "A Story") is True
        assert story_title_exists(session, "Another Story") is False


def test_story_title_exists_true_for_archived_story():
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A brief")
        archive_story(session, story.id)

    with session_scope() as session:
        assert story_title_exists(session, "A Story") is True


def test_import_story_creates_story_with_given_title():
    with session_scope() as session:
        story_id = import_story(session, VALID_DATA, "Renamed Story")

    with session_scope() as session:
        exported = build_story_export_data(session, story_id)

    assert exported["story"]["title"] == "Renamed Story"
    assert exported["story"]["story_brief"] == "A brief"


def test_import_story_creates_characters_and_locations():
    with session_scope() as session:
        story_id = import_story(session, VALID_DATA, "A Story")

    with session_scope() as session:
        exported = build_story_export_data(session, story_id)

    assert exported["characters"] == [{"name": "Alex", "description": "Hero", "motive": "Justice"}]
    assert exported["locations"] == [{"name": "The Keep", "description": "An old fortress"}]


def test_import_story_positions_scenes_sequentially_by_list_order_ignoring_file_positions():
    data = yaml.safe_load(yaml.safe_dump(VALID_DATA))
    data["scenes"] = [
        {**data["scenes"][0], "position": 99, "brief": "First"},
        {**data["scenes"][0], "position": 1, "brief": "Second", "pov_character": None, "characters": [], "locations": []},
    ]

    with session_scope() as session:
        story_id = import_story(session, data, "A Story")

    with session_scope() as session:
        exported = build_story_export_data(session, story_id)

    assert [scene["brief"] for scene in exported["scenes"]] == ["First", "Second"]
    assert [scene["position"] for scene in exported["scenes"]] == [0, 1]


def test_import_story_resolves_pov_and_assignments_by_name():
    with session_scope() as session:
        story_id = import_story(session, VALID_DATA, "A Story")

    with session_scope() as session:
        exported = build_story_export_data(session, story_id)

    scene = exported["scenes"][0]
    assert scene["pov_character"] == "Alex"
    assert scene["characters"] == ["Alex"]
    assert scene["locations"] == ["The Keep"]


def test_import_story_archives_when_is_archived_true():
    data = yaml.safe_load(yaml.safe_dump(VALID_DATA))
    data["story"]["is_archived"] = True

    with session_scope() as session:
        story_id = import_story(session, data, "A Story")

    with session_scope() as session:
        exported = build_story_export_data(session, story_id)

    assert exported["story"]["is_archived"] is True


def test_import_story_leaves_unarchived_when_is_archived_false():
    with session_scope() as session:
        story_id = import_story(session, VALID_DATA, "A Story")

    with session_scope() as session:
        exported = build_story_export_data(session, story_id)

    assert exported["story"]["is_archived"] is False


def test_import_story_round_trip_matches_original_data_except_title():
    with session_scope() as session:
        story = create_story(session, title="Original", story_brief="A brief", style_guidance="Style")
        character = create_character(session, story_id=story.id, name="Alex", description="Hero", motive="Justice")
        location = create_location(session, story_id=story.id, name="The Keep", description="An old fortress")
        scene = create_scene(
            session,
            story_id=story.id,
            position=0,
            brief="Opening",
            heading="Chapter One",
            pov_character_id=character.id,
        )
        assign_character(session, scene.id, character.id)
        assign_location(session, scene.id, location.id)
        original_story_id = story.id

    with session_scope() as session:
        original_export = build_story_export_data(session, original_story_id)

    with session_scope() as session:
        new_story_id = import_story(session, original_export, "Reimported")

    with session_scope() as session:
        reimported_export = build_story_export_data(session, new_story_id)

    expected = {**original_export, "story": {**original_export["story"], "title": "Reimported"}}
    assert reimported_export == expected


def test_duplicate_story_title_dialog_prefills_title_with_continue_enabled(qtbot):
    dialog = DuplicateStoryTitleDialog("A Story")
    qtbot.addWidget(dialog)

    assert dialog.title_edit.text() == "A Story"
    assert dialog.continue_button.isEnabled()
    assert dialog.new_title() == "A Story"


def test_duplicate_story_title_dialog_disables_continue_when_title_blank(qtbot):
    dialog = DuplicateStoryTitleDialog("A Story")
    qtbot.addWidget(dialog)

    dialog.title_edit.setText("   ")

    assert not dialog.continue_button.isEnabled()


def test_duplicate_story_title_dialog_continue_button_accepts_with_new_title(qtbot):
    dialog = DuplicateStoryTitleDialog("A Story")
    qtbot.addWidget(dialog)
    dialog.title_edit.setText("A New Title")

    dialog.continue_button.clicked.emit()

    assert dialog.result() == dialog.DialogCode.Accepted
    assert dialog.new_title() == "A New Title"


def test_duplicate_story_title_dialog_cancel_button_rejects(qtbot):
    dialog = DuplicateStoryTitleDialog("A Story")
    qtbot.addWidget(dialog)

    dialog.cancel_button.clicked.emit()

    assert dialog.result() == dialog.DialogCode.Rejected
