from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from scene.core.scene import list_scenes
from scene.data.database import session_scope

if TYPE_CHECKING:
    from scene.gui.main_window import MainWindow

CONFIRM_TEXT = (
    "This will render every scene in the story, one at a time, replacing each scene's active "
    "rendering with a newly generated one. You'll be able to watch each scene render, and can "
    "cancel at any point to stop the whole run."
)
SCENES_TAB_LABEL = "Scenes"


class RenderFullStoryConfirmDialog(QDialog):
    """Confirms a full-story render before it starts, mirroring `RenderingColumn`'s
    `_PromptPreviewDialog` button convention (Cancel then Proceed, Proceed accepts)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Render Full Story")
        self.setModal(True)

        message_label = QLabel(CONFIRM_TEXT)
        message_label.setWordWrap(True)
        message_label.setMaximumWidth(360)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        self.proceed_button = QPushButton("Proceed")
        self.proceed_button.clicked.connect(self.accept)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.proceed_button)

        layout = QVBoxLayout(self)
        layout.addWidget(message_label)
        layout.addLayout(button_row)


class FullStoryRenderController(QObject):
    """Drives a sequential, unattended re-render of every scene in a story, reusing
    `RenderingColumn`'s existing single-scene generate/cancel/continuity machinery so the user
    watches each scene render live exactly as they would manually. Advancing to the next scene
    waits for the current one to fully settle (render, plus its continuity snapshot if
    configured) via `RenderingColumn.scene_settled`.

    Stops (emitting `finished`) if a scene is cancelled or errors, if the active story changes
    out from under it, if a scene can no longer be found in the entity column's scene list, or
    once every scene has been rendered.
    """

    finished = Signal()

    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self._scene_ids: list[int] = []
        self._index = 0
        self._story_id: int | None = None

    def start(self, story_id: int) -> None:
        self._story_id = story_id
        with session_scope() as session:
            self._scene_ids = [scene.id for scene in list_scenes(session, story_id)]
        self._index = 0
        self._main_window.rendering_column.scene_settled.connect(self._on_scene_settled)
        self._switch_to_scenes_tab()
        self._advance()

    def _switch_to_scenes_tab(self) -> None:
        tabs = self._main_window.entity_column.tabs
        for index in range(tabs.count()):
            if tabs.tabText(index) == SCENES_TAB_LABEL:
                tabs.setCurrentIndex(index)
                return

    def _advance(self) -> None:
        if self._main_window.current_story_id != self._story_id or self._index >= len(self._scene_ids):
            self._finish()
            return
        if not self._select_scene(self._scene_ids[self._index]):
            self._finish()
            return
        if not self._main_window.rendering_column.generate_now():
            self._finish()

    def _select_scene(self, scene_id: int) -> bool:
        list_widget = self._main_window.entity_column.scenes.list_widget
        for row in range(list_widget.count()):
            item = list_widget.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == scene_id:
                list_widget.setCurrentRow(row)
                return True
        return False

    def _on_scene_settled(self) -> None:
        rendering_column = self._main_window.rendering_column
        if rendering_column.last_generation_cancelled or rendering_column.last_generation_error is not None:
            self._finish()
            return
        self._index += 1
        self._advance()

    def _finish(self) -> None:
        self._main_window.rendering_column.scene_settled.disconnect(self._on_scene_settled)
        self.finished.emit()
