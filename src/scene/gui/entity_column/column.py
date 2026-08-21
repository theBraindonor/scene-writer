from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QScrollArea, QStackedWidget, QTabWidget, QVBoxLayout, QWidget

from scene.gui.entity_column.characters import CharactersWidget
from scene.gui.entity_column.locations import LocationsWidget
from scene.gui.entity_column.scenes import ScenesWidget
from scene.gui.entity_column.story_detail import StoryDetailWidget


def _wrap_in_scroll(widget: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(widget)
    return scroll


class EntityColumn(QWidget):
    """The entity column: Story/Characters/Locations/Scenes tabs.

    Shows an empty-state message until a story is selected (via `set_story`, which
    `MainWindow` connects to its own `current_story_changed` signal). Tracks the selected
    scene as `current_scene_id`, emitting `current_scene_changed` on every change — the
    interface `e003`'s rendering column connects to.
    """

    current_scene_changed = Signal(object)  # int | None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.current_story_id: int | None = None
        self.current_scene_id: int | None = None

        self.empty_label = QLabel("Select or create a story to see its details.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.story_detail = StoryDetailWidget()
        self.scenes = ScenesWidget()
        self.characters = CharactersWidget()
        self.locations = LocationsWidget()

        self.scenes.scene_selected.connect(self._on_scene_selected)
        self.characters.characters_changed.connect(self.scenes.refresh_assignment_options)
        self.locations.locations_changed.connect(self.scenes.refresh_assignment_options)

        self.tabs = QTabWidget()
        self.tabs.addTab(_wrap_in_scroll(self.story_detail), "Story")
        self.tabs.addTab(_wrap_in_scroll(self.characters), "Characters")
        self.tabs.addTab(_wrap_in_scroll(self.locations), "Locations")
        self.tabs.addTab(_wrap_in_scroll(self.scenes), "Scenes")

        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty_label)
        self.stack.addWidget(self.tabs)

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

    def set_story(self, story_id: int | None) -> None:
        self.current_story_id = story_id
        if story_id is None:
            self.stack.setCurrentWidget(self.empty_label)
            self._set_current_scene(None)
            return
        self.stack.setCurrentWidget(self.tabs)
        self.story_detail.load(story_id)
        # Scenes loads first so its current-scene selection resets to None for the new story
        # before Characters/Locations trigger refresh_assignment_options() below — otherwise
        # that refresh could run against a scene id left over from the previous story.
        self.scenes.load(story_id)
        self.characters.load(story_id)
        self.locations.load(story_id)

    def _on_scene_selected(self, scene_id: int | None) -> None:
        self._set_current_scene(scene_id)

    def _set_current_scene(self, scene_id: int | None) -> None:
        self.current_scene_id = scene_id
        self.current_scene_changed.emit(scene_id)
