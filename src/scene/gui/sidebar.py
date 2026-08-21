from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scene.core.story import create_story as create_story_record
from scene.core.story import list_stories
from scene.data.database import session_scope
from scene.gui.section_heading import section_heading


class NewStoryDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Story")

        self.title_edit = QLineEdit()
        self.scenario_edit = QPlainTextEdit()
        self.style_guidance_edit = QPlainTextEdit()

        form = QFormLayout()
        form.addRow("Title", self.title_edit)
        form.addRow("Scenario", self.scenario_edit)
        form.addRow("Style Guidance", self.style_guidance_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str, str | None]:
        title = self.title_edit.text().strip()
        scenario = self.scenario_edit.toPlainText().strip()
        style_guidance = self.style_guidance_edit.toPlainText().strip() or None
        return title, scenario, style_guidance


class Sidebar(QWidget):
    """Story picker pane: list, select, and create stories.

    Emits `story_selected` on selection changes and `collapse_toggled` from its
    toggle button. `collapse_button` is constructed here but deliberately left
    unparented into this widget's own layout: this pane's width is driven to
    zero on collapse, and a button laid out inside it would shrink to zero
    width right along with it, making it unclickable to expand again. The
    containing window is expected to place `collapse_button` somewhere that
    stays visible regardless of this pane's collapsed state (e.g. a header
    row above the splitter), and to translate its `collapse_toggled` signal
    into actual pane width — this widget has no knowledge of the QSplitter
    that hosts it.
    """

    story_selected = Signal(object)  # int | None
    collapse_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.collapse_button = QPushButton("Collapse")
        self.collapse_button.setCheckable(True)
        self.collapse_button.toggled.connect(self._on_collapse_toggled)

        self.story_list = QListWidget()
        self.story_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.story_list.currentItemChanged.connect(self._on_current_item_changed)

        self.new_story_button = QPushButton("New Story")
        self.new_story_button.clicked.connect(self._on_new_story_clicked)

        layout = QVBoxLayout(self)
        layout.addWidget(section_heading("Stories"))
        layout.addWidget(self.story_list)
        layout.addWidget(self.new_story_button)

        self.refresh_stories()

    def refresh_stories(self, select_story_id: int | None = None) -> None:
        self.story_list.blockSignals(True)
        self.story_list.clear()
        with session_scope() as session:
            for story in list_stories(session):
                item = QListWidgetItem(story.title)
                item.setData(Qt.ItemDataRole.UserRole, story.id)
                self.story_list.addItem(item)
                if story.id == select_story_id:
                    self.story_list.setCurrentItem(item)
        self.story_list.blockSignals(False)
        if select_story_id is not None:
            self.story_selected.emit(select_story_id)

    def create_story(self, title: str, scenario: str, style_guidance: str | None = None) -> None:
        with session_scope() as session:
            story = create_story_record(session, title=title, scenario=scenario, style_guidance=style_guidance)
            story_id = story.id
        self.refresh_stories(select_story_id=story_id)

    def _on_current_item_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        story_id = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        self.story_selected.emit(story_id)

    def _on_new_story_clicked(self) -> None:
        values = self._prompt_new_story()
        if values is None:
            return
        title, scenario, style_guidance = values
        self.create_story(title, scenario, style_guidance)

    def _prompt_new_story(self) -> tuple[str, str, str | None] | None:
        dialog = NewStoryDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.values()

    def _on_collapse_toggled(self, collapsed: bool) -> None:
        self.collapse_button.setText("Expand" if collapsed else "Collapse")
        self.collapse_toggled.emit(collapsed)
