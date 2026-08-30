from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ApplicationTab(Enum):
    STORY = "story"
    CHARACTERS = "characters"
    LOCATIONS = "locations"
    SCENES = "scenes"


@dataclass
class ApplicationState:
    history: list[dict[str, Any]] = field(default_factory=list)
    current_story_id: int | None = None
    current_tab: ApplicationTab | None = None
    current_character_id: int | None = None
    current_location_id: int | None = None
    current_scene_id: int | None = None
