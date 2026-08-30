import os

import yaml
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget
from sqlalchemy.orm import Session

from scene.core.character import list_characters
from scene.core.location import list_locations
from scene.core.scene import list_scenes
from scene.core.scene_character import list_characters_for_scene
from scene.core.scene_location import list_locations_for_scene
from scene.core.story import get_story

EXPORT_DIALOG_TITLE = "Export Story"
EXPORT_FILE_FILTER = "YAML Files (*.yaml *.yml);;All Files (*)"
DEFAULT_EXTENSION = ".yaml"
EXPORT_ERROR_TITLE = "Export Story"
EXPORT_ERROR_TEXT = "Could not export the story: {error}"


def build_story_export_data(session: Session, story_id: int) -> dict:
    """Assemble a story's full planning data — the story's own fields, its characters, its
    locations, and its scenes (each scene's assigned characters/locations and POV character
    referenced by name rather than internal database id) — as a plain dict ready for YAML
    serialization. Deliberately excludes renderings and continuity snapshots."""
    story = get_story(session, story_id)
    if story is None:
        raise ValueError(f"Story {story_id} not found")

    characters_by_id = {character.id: character for character in list_characters(session, story_id)}

    scenes = []
    for scene in list_scenes(session, story_id):
        pov_character = characters_by_id.get(scene.pov_character_id)
        scenes.append(
            {
                "position": scene.position,
                "heading": scene.heading,
                "brief": scene.brief,
                "required_actions": scene.required_actions,
                "desired_outcome": scene.desired_outcome,
                "target_length": scene.target_length,
                "pov_character": pov_character.name if pov_character else None,
                "characters": [character.name for character in list_characters_for_scene(session, scene.id)],
                "locations": [location.name for location in list_locations_for_scene(session, scene.id)],
            }
        )

    return {
        "story": {
            "title": story.title,
            "story_brief": story.story_brief,
            "style_guidance": story.style_guidance,
            "generation_guideance": story.generation_guideance,
            "is_archived": bool(story.is_archived),
        },
        "characters": [
            {"name": character.name, "description": character.description, "motive": character.motive}
            for character in characters_by_id.values()
        ],
        "locations": [
            {"name": location.name, "description": location.description}
            for location in list_locations(session, story_id)
        ],
        "scenes": scenes,
    }


def save_yaml_to_file(parent: QWidget, data: dict) -> bool:
    """Prompt for a save path and write `data` to it as YAML. Returns False without touching the
    filesystem if the dialog is cancelled, True on success, and False (after showing an error) if
    the write fails."""
    path, _ = QFileDialog.getSaveFileName(parent, EXPORT_DIALOG_TITLE, "", EXPORT_FILE_FILTER)
    if not path:
        return False
    if not os.path.splitext(path)[1]:
        path += DEFAULT_EXTENSION
    try:
        with open(path, "w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, sort_keys=False, allow_unicode=True)
    except OSError as error:
        QMessageBox.critical(parent, EXPORT_ERROR_TITLE, EXPORT_ERROR_TEXT.format(error=error))
        return False
    return True
