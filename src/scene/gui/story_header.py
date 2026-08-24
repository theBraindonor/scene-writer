from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scene.core.story import create_story as create_story_record
from scene.core.story import get_story, list_stories
from scene.data.database import session_scope

NO_STORY_SELECTED_TEXT = "No story selected"


class NewStoryDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Story")

        self.title_edit = QLineEdit()
        self.story_brief_edit = QPlainTextEdit()
        self.style_guidance_edit = QPlainTextEdit()

        form = QFormLayout()
        form.addRow("Title", self.title_edit)
        form.addRow("Story Brief", self.story_brief_edit)
        form.addRow("Style Guidance", self.style_guidance_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str, str | None]:
        title = self.title_edit.text().strip()
        story_brief = self.story_brief_edit.toPlainText().strip()
        style_guidance = self.style_guidance_edit.toPlainText().strip() or None
        return title, story_brief, style_guidance


class StoryPickerDialog(QDialog):
    """Modal story picker: pick a story from the database, optionally including archived ones."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open Story")

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_current_item_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.include_archived_checkbox = QCheckBox("Include archived")
        self.include_archived_checkbox.toggled.connect(self._on_include_archived_toggled)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self.include_archived_checkbox)
        bottom_row.addStretch()
        bottom_row.addWidget(self.button_box)

        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget)
        layout.addLayout(bottom_row)

        self._refresh_list()

    def selected_story_id(self) -> int | None:
        current = self.list_widget.currentItem()
        return current.data(Qt.ItemDataRole.UserRole) if current is not None else None

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        with session_scope() as session:
            for story in list_stories(session, include_archived=self.include_archived_checkbox.isChecked()):
                item = QListWidgetItem(story.title)
                item.setData(Qt.ItemDataRole.UserRole, story.id)
                self.list_widget.addItem(item)

    def _on_include_archived_toggled(self, _checked: bool) -> None:
        self._refresh_list()

    def _on_current_item_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(current is not None)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self.accept()


class StoryHeader(QWidget):
    """Always-visible header: shows the current story's title and launches story creation/selection.

    Emits `story_selected` when a story is created via "New Story" or chosen via "Open"'s modal
    picker. `set_current_story` only updates the displayed label and never emits `story_selected`,
    so callers (e.g. `MainWindow` syncing to a selection that originated elsewhere, such as a chat
    turn) can call it without triggering a feedback loop.
    """

    story_selected = Signal(object)  # int

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.story_label = QLabel(NO_STORY_SELECTED_TEXT)

        self.new_story_button = QPushButton("New")
        self.new_story_button.clicked.connect(self._on_new_story_clicked)

        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self._on_open_clicked)

        layout = QHBoxLayout(self)
        layout.addWidget(self.story_label)
        layout.addWidget(self.new_story_button)
        layout.addWidget(self.open_button)
        layout.addStretch()

    def set_current_story(self, story_id: int | None) -> None:
        story = None
        if story_id is not None:
            with session_scope() as session:
                story = get_story(session, story_id)
        self.story_label.setText(story.title if story is not None else NO_STORY_SELECTED_TEXT)

    def _on_new_story_clicked(self) -> None:
        values = self._prompt_new_story()
        if values is None:
            return
        title, story_brief, style_guidance = values
        with session_scope() as session:
            story = create_story_record(
                session, title=title, story_brief=story_brief, style_guidance=style_guidance
            )
            story_id = story.id
        self.story_selected.emit(story_id)

    def _prompt_new_story(self) -> tuple[str, str, str | None] | None:
        dialog = NewStoryDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.values()

    def _on_open_clicked(self) -> None:
        story_id = self._prompt_story_picker()
        if story_id is None:
            return
        self.story_selected.emit(story_id)

    def _prompt_story_picker(self) -> int | None:
        dialog = StoryPickerDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.selected_story_id()
