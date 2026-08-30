import pytest
import yaml
from PySide6.QtWidgets import QFileDialog, QMessageBox

import scene.data.database as database_module
from scene.core.character import create_character
from scene.core.continuity_snapshot import create_snapshot
from scene.core.location import create_location
from scene.core.rendering import create_rendering, set_active_rendering
from scene.core.scene import create_scene
from scene.core.scene_character import assign_character
from scene.core.scene_location import assign_location
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.story_export import build_story_export_data, save_yaml_to_file


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_story():
    with session_scope() as session:
        story = create_story(
            session,
            title="A Story",
            story_brief="A story brief",
            style_guidance="Style",
            generation_guideance="Guidance",
        )
        return story.id


def test_build_story_export_data_includes_story_characters_locations_and_scenes():
    story_id = seed_story()
    with session_scope() as session:
        character = create_character(session, story_id=story_id, name="Alex", description="Hero", motive="Justice")
        location = create_location(session, story_id=story_id, name="The Keep", description="An old fortress")
        scene = create_scene(
            session,
            story_id=story_id,
            position=0,
            brief="Opening",
            heading="Chapter One",
            required_actions="Must arrive",
            desired_outcome="Sets the stage",
            target_length="short",
            pov_character_id=character.id,
        )
        assign_character(session, scene.id, character.id)
        assign_location(session, scene.id, location.id)

    with session_scope() as session:
        data = build_story_export_data(session, story_id)

    assert data == {
        "story": {
            "title": "A Story",
            "story_brief": "A story brief",
            "style_guidance": "Style",
            "generation_guideance": "Guidance",
            "is_archived": False,
        },
        "characters": [{"name": "Alex", "description": "Hero", "motive": "Justice"}],
        "locations": [{"name": "The Keep", "description": "An old fortress"}],
        "scenes": [
            {
                "position": 0,
                "heading": "Chapter One",
                "brief": "Opening",
                "required_actions": "Must arrive",
                "desired_outcome": "Sets the stage",
                "target_length": "short",
                "pov_character": "Alex",
                "characters": ["Alex"],
                "locations": ["The Keep"],
            }
        ],
    }


def test_build_story_export_data_handles_scene_with_no_pov_or_assignments():
    story_id = seed_story()
    with session_scope() as session:
        create_scene(session, story_id=story_id, position=0, brief="Opening")

    with session_scope() as session:
        data = build_story_export_data(session, story_id)

    scene = data["scenes"][0]
    assert scene["pov_character"] is None
    assert scene["characters"] == []
    assert scene["locations"] == []


def test_build_story_export_data_orders_scenes_by_position():
    story_id = seed_story()
    with session_scope() as session:
        create_scene(session, story_id=story_id, position=1, brief="Second")
        create_scene(session, story_id=story_id, position=0, brief="First")

    with session_scope() as session:
        data = build_story_export_data(session, story_id)

    assert [scene["brief"] for scene in data["scenes"]] == ["First", "Second"]


def test_build_story_export_data_raises_for_missing_story():
    with session_scope() as session, pytest.raises(ValueError, match="Story 999 not found"):
        build_story_export_data(session, 999)


def test_build_story_export_data_excludes_renderings_and_continuity_snapshots():
    story_id = seed_story()
    with session_scope() as session:
        scene = create_scene(session, story_id=story_id, position=0, brief="Opening")
        rendering = create_rendering(session, scene_id=scene.id, body="Once upon a time.")
        set_active_rendering(session, rendering.id)
        create_snapshot(session, story_id=story_id, through_scene_id=scene.id, narrative_state="State")

    with session_scope() as session:
        data = build_story_export_data(session, story_id)

    serialized = yaml.safe_dump(data)
    assert "Once upon a time." not in serialized
    assert "narrative_state" not in serialized
    assert "State" not in serialized


def test_save_yaml_to_file_writes_the_chosen_path(tmp_path, monkeypatch):
    target = tmp_path / "story.yaml"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target), ""))
    data = {"story": {"title": "A Story"}}

    result = save_yaml_to_file(None, data)

    assert result is True
    assert yaml.safe_load(target.read_text(encoding="utf-8")) == data


def test_save_yaml_to_file_returns_false_without_writing_when_cancelled(tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: ("", ""))

    result = save_yaml_to_file(None, {"story": {"title": "A Story"}})

    assert result is False
    assert list(tmp_path.iterdir()) == []


def test_save_yaml_to_file_appends_yaml_extension_when_missing(tmp_path, monkeypatch):
    target = tmp_path / "story"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target), ""))
    data = {"story": {"title": "A Story"}}

    result = save_yaml_to_file(None, data)

    assert result is True
    assert yaml.safe_load((tmp_path / "story.yaml").read_text(encoding="utf-8")) == data


def test_save_yaml_to_file_shows_error_and_returns_false_on_write_failure(tmp_path, monkeypatch):
    target = tmp_path / "missing-dir" / "story.yaml"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target), ""))
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: shown.append(args[1:]))

    result = save_yaml_to_file(None, {"story": {"title": "A Story"}})

    assert result is False
    assert shown
