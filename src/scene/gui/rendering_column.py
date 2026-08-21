from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QStackedWidget, QVBoxLayout, QWidget

from scene.core.rendering import list_renderings
from scene.data.database import session_scope
from scene.gui.section_heading import section_heading

NO_SCENE_SELECTED_TEXT = "Select a scene to see its rendering."
NO_RENDERINGS_TEXT = "This scene has no renderings yet."


class RenderingColumn(QWidget):
    """Read-only display of the selected scene's active rendering.

    Connects to `MainWindow.current_story_changed` and `EntityColumn.current_scene_changed` —
    switching stories resets the selected scene to `None`, so both signals drive the same
    `set_scene` reset. No editing, generation, or version browsing here: per the campaign's
    scope, that stays on `scene-coordinator render` until a later campaign brings rendering
    workflows into the GUI.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.current_scene_id: int | None = None

        self.no_selection_label = QLabel(NO_SCENE_SELECTED_TEXT)
        self.no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_selection_label.setWordWrap(True)

        self.no_renderings_label = QLabel(NO_RENDERINGS_TEXT)
        self.no_renderings_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_renderings_label.setWordWrap(True)

        self.body_view = QPlainTextEdit()
        self.body_view.setReadOnly(True)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.no_selection_label)
        self.stack.addWidget(self.no_renderings_label)
        self.stack.addWidget(self.body_view)

        layout = QVBoxLayout(self)
        layout.addWidget(section_heading("Rendering"))
        layout.addWidget(self.stack)

    def set_scene(self, scene_id: int | None) -> None:
        self.current_scene_id = scene_id
        if scene_id is None:
            self.stack.setCurrentWidget(self.no_selection_label)
            return
        with session_scope() as session:
            renderings = list_renderings(session, scene_id)
        active = next((rendering for rendering in renderings if rendering.is_active), None)
        if active is None:
            self.stack.setCurrentWidget(self.no_renderings_label)
            return
        self.body_view.setPlainText(active.body)
        self.stack.setCurrentWidget(self.body_view)
