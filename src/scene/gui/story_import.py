import yaml
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
from sqlalchemy.orm import Session

from scene.core.character import create_character
from scene.core.location import create_location
from scene.core.scene import create_scene
from scene.core.scene_character import assign_character
from scene.core.scene_location import assign_location
from scene.core.story import archive_story, create_story, list_stories


def parse_story_import_file(path: str) -> dict:
    """Read and validate a YAML file previously written by Export Story... Raises ValueError with
    a user-facing message if the file can't be read, isn't valid YAML, or is missing/malformed
    required data. Returns the parsed dict unchanged on success."""
    try:
        with open(path, encoding="utf-8") as file:
            raw = yaml.safe_load(file)
    except OSError as error:
        raise ValueError(f"Could not read the file: {error}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"The file is not valid YAML: {error}") from error

    if not isinstance(raw, dict):
        raise ValueError("The file does not contain a story export.")  # noqa: TRY004 - user-facing file error

    story = raw.get("story")
    if (
        not isinstance(story, dict)
        or not str(story.get("title") or "").strip()
        or not str(story.get("story_brief") or "").strip()
    ):
        raise ValueError("The file is missing a story title or story brief.")

    characters = raw.get("characters", [])
    locations = raw.get("locations", [])
    scenes = raw.get("scenes", [])
    if not isinstance(characters, list) or not isinstance(locations, list) or not isinstance(scenes, list):
        raise ValueError("The file's characters, locations, or scenes are malformed.")  # noqa: TRY004

    character_names: set[str] = set()
    for character in characters:
        if not isinstance(character, dict) or not str(character.get("name") or "").strip():
            raise ValueError("A character in the file is missing its name.")
        if character["name"] in character_names:
            raise ValueError(f"The file lists character {character['name']!r} more than once.")
        character_names.add(character["name"])

    location_names: set[str] = set()
    for location in locations:
        if not isinstance(location, dict) or not str(location.get("name") or "").strip():
            raise ValueError("A location in the file is missing its name.")
        if location["name"] in location_names:
            raise ValueError(f"The file lists location {location['name']!r} more than once.")
        location_names.add(location["name"])

    for scene in scenes:
        if not isinstance(scene, dict) or not str(scene.get("brief") or "").strip():
            raise ValueError("A scene in the file is missing its brief.")
        pov = scene.get("pov_character")
        if pov is not None and pov not in character_names:
            raise ValueError(f"A scene references unknown POV character {pov!r}.")
        for name in scene.get("characters") or []:
            if name not in character_names:
                raise ValueError(f"A scene references unknown character {name!r}.")
        for name in scene.get("locations") or []:
            if name not in location_names:
                raise ValueError(f"A scene references unknown location {name!r}.")

    return raw


def story_title_exists(session: Session, title: str) -> bool:
    return any(story.title == title for story in list_stories(session, include_archived=True))


def import_story(session: Session, data: dict, title: str) -> int:
    """Create a new story (and its characters, locations, and scenes) from previously-validated
    export data, using `title` for the new story's title (which may differ from the file's
    original title if it collided with an existing story). Scenes are (re)positioned sequentially
    in the order they appear in `data["scenes"]`, regardless of any `position` value in the file.
    """
    story_data = data["story"]
    story = create_story(
        session,
        title=title,
        story_brief=story_data["story_brief"],
        style_guidance=story_data.get("style_guidance"),
        generation_guideance=story_data.get("generation_guideance"),
    )

    characters_by_name = {
        character["name"]: create_character(
            session,
            story_id=story.id,
            name=character["name"],
            description=character.get("description"),
            motive=character.get("motive"),
        )
        for character in data.get("characters", [])
    }
    locations_by_name = {
        location["name"]: create_location(
            session, story_id=story.id, name=location["name"], description=location.get("description")
        )
        for location in data.get("locations", [])
    }

    for position, scene in enumerate(data.get("scenes", [])):
        pov = scene.get("pov_character")
        record = create_scene(
            session,
            story_id=story.id,
            position=position,
            brief=scene["brief"],
            heading=scene.get("heading"),
            required_actions=scene.get("required_actions"),
            target_length=scene.get("target_length"),
            desired_outcome=scene.get("desired_outcome"),
            pov_character_id=characters_by_name[pov].id if pov else None,
        )
        for name in scene.get("characters") or []:
            assign_character(session, record.id, characters_by_name[name].id)
        for name in scene.get("locations") or []:
            assign_location(session, record.id, locations_by_name[name].id)

    if story_data.get("is_archived"):
        archive_story(session, story.id)

    return story.id


class DuplicateStoryTitleDialog(QDialog):
    """Prompts for a replacement title when Import Story... finds one already taken, mirroring
    `RenderFullStoryConfirmDialog`'s Cancel/Proceed button order and semantics (Continue here,
    since this dialog collects new input rather than just confirming an action)."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Story")
        self.setModal(True)

        message = QLabel(f'A story named "{title}" already exists. Enter a different title to continue the import.')
        message.setWordWrap(True)

        self.title_edit = QLineEdit(title)
        self.title_edit.textChanged.connect(self._update_continue_enabled)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.continue_button = QPushButton("Continue")
        self.continue_button.clicked.connect(self.accept)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.continue_button)

        layout = QVBoxLayout(self)
        layout.addWidget(message)
        layout.addWidget(self.title_edit)
        layout.addLayout(button_row)

        self._update_continue_enabled()

    def _update_continue_enabled(self) -> None:
        self.continue_button.setEnabled(bool(self.title_edit.text().strip()))

    def new_title(self) -> str:
        return self.title_edit.text().strip()
