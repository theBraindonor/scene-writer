import os

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from scene.core.rendering import list_renderings
from scene.core.scene import list_scenes
from scene.gui.rendering_column import BODY_FONT_SCALE

DIALOG_WIDTH = 900
DIALOG_HEIGHT = 700
SAVE_DIALOG_TITLE = "Save Full Story"
SAVE_FILE_FILTER = "Text Files (*.txt);;All Files (*)"
DEFAULT_EXTENSION = ".txt"
SAVE_ERROR_TITLE = "Save Full Story"
SAVE_ERROR_TEXT = "Could not save the file: {error}"


SCENE_SEPARATOR = "\n\n---\n\n"


def combine_story_prose(session: Session, story_id: int) -> str:
    """Join every scene's currently-active rendering body, in scene position order, separated by
    a markdown horizontal rule as a soft between-scenes marker. Scenes with no active rendering
    are skipped rather than erroring."""
    sections = []
    for scene in list_scenes(session, story_id):
        active = next((rendering for rendering in list_renderings(session, scene.id) if rendering.is_active), None)
        if active is not None:
            sections.append(active.body)
    return SCENE_SEPARATOR.join(sections)


def save_text_to_file(parent: QWidget, text: str) -> bool:
    """Prompt for a save path and write `text` to it as UTF-8. Returns False without touching
    the filesystem if the dialog is cancelled, True on success, and False (after showing an
    error) if the write fails."""
    path, _ = QFileDialog.getSaveFileName(parent, SAVE_DIALOG_TITLE, "", SAVE_FILE_FILTER)
    if not path:
        return False
    if not os.path.splitext(path)[1]:
        path += DEFAULT_EXTENSION
    try:
        with open(path, "w", encoding="utf-8") as file:
            file.write(text)
    except OSError as error:
        QMessageBox.critical(parent, SAVE_ERROR_TITLE, SAVE_ERROR_TEXT.format(error=error))
        return False
    return True


class FullStoryDialog(QDialog):
    """Large modal viewer for a story's combined prose (Render > View Full Story...), showing
    the text at the same scaled font as `RenderingColumn.body_view`. Its Save... button reuses
    `save_text_to_file`, the same routine Render > Save Full Story... calls directly."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("View Full Story")
        self.setModal(True)
        self.resize(DIALOG_WIDTH, DIALOG_HEIGHT)

        self._text = text

        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setPlainText(text)
        font = self.text_view.font()
        font.setPointSize(round(font.pointSize() * BODY_FONT_SCALE))
        self.text_view.setFont(font)

        self.save_button = QPushButton("Save...")
        self.save_button.clicked.connect(self._on_save_clicked)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.text_view)
        layout.addLayout(button_row)

    def _on_save_clicked(self) -> None:
        save_text_to_file(self, self._text)
