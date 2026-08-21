from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scene.core.character import create_character, delete_character, list_characters, update_character
from scene.data.database import session_scope
from scene.gui.list_sizing import fit_list_height_to_contents
from scene.gui.section_heading import section_heading


class CharactersWidget(QWidget):
    """List, create, edit, and delete a story's characters.

    Emits `characters_changed` after every list refresh so the Scenes section can keep its
    character-assignment checklist in sync without polling.
    """

    characters_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.story_id: int | None = None
        self.current_character_id: int | None = None

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_current_item_changed)

        self.name_edit = QLineEdit()
        self.description_edit = QPlainTextEdit()
        self.motive_edit = QPlainTextEdit()

        self.new_button = QPushButton("New Character")
        self.new_button.clicked.connect(self._on_new_clicked)

        self.save_button = QPushButton("Save Character")
        self.save_button.clicked.connect(self._on_save_clicked)

        self.delete_button = QPushButton("Delete Character")
        self.delete_button.clicked.connect(self._on_delete_clicked)

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Motive", self.motive_edit)

        buttons = QHBoxLayout()
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.delete_button)

        layout = QVBoxLayout(self)
        layout.addWidget(section_heading("Characters"))
        layout.addWidget(self.list_widget)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def load(self, story_id: int) -> None:
        self.story_id = story_id
        self.refresh()

    def refresh(self, select_character_id: int | None = None) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        with session_scope() as session:
            for character in list_characters(session, self.story_id):
                item = QListWidgetItem(character.name)
                item.setData(Qt.ItemDataRole.UserRole, character.id)
                self.list_widget.addItem(item)
                if character.id == select_character_id:
                    self.list_widget.setCurrentItem(item)
        self.list_widget.blockSignals(False)
        fit_list_height_to_contents(self.list_widget)
        self._load_detail(select_character_id)
        self.characters_changed.emit()

    def _on_current_item_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        character_id = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        self._load_detail(character_id)

    def _load_detail(self, character_id: int | None) -> None:
        self.current_character_id = character_id
        if character_id is None:
            self.name_edit.clear()
            self.description_edit.clear()
            self.motive_edit.clear()
            return
        with session_scope() as session:
            characters = {character.id: character for character in list_characters(session, self.story_id)}
        character = characters.get(character_id)
        if character is None:
            return
        self.name_edit.setText(character.name)
        self.description_edit.setPlainText(character.description or "")
        self.motive_edit.setPlainText(character.motive or "")

    def _on_new_clicked(self) -> None:
        if self.story_id is None:
            return
        with session_scope() as session:
            character = create_character(session, story_id=self.story_id, name="New Character")
            character_id = character.id
        self.refresh(select_character_id=character_id)

    def _on_save_clicked(self) -> None:
        if self.current_character_id is None:
            return
        with session_scope() as session:
            update_character(
                session,
                self.current_character_id,
                name=self.name_edit.text().strip(),
                description=self.description_edit.toPlainText().strip(),
                motive=self.motive_edit.toPlainText().strip(),
            )
        self.refresh(select_character_id=self.current_character_id)

    def _on_delete_clicked(self) -> None:
        if self.current_character_id is None:
            return
        if not self._confirm_delete(self.name_edit.text()):
            return
        with session_scope() as session:
            delete_character(session, self.current_character_id)
        self.refresh()

    def _confirm_delete(self, name: str) -> bool:
        answer = QMessageBox.question(
            self,
            "Delete Character",
            f"Delete character '{name}'? This cannot be undone.",
        )
        return answer == QMessageBox.StandardButton.Yes
