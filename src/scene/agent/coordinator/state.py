from dataclasses import dataclass, field
from typing import Any


@dataclass
class CoordinatorState:
    history: list[dict[str, Any]] = field(default_factory=list)
    current_story_id: int | None = None
