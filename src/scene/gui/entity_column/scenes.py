from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from scene.core.character import list_characters
from scene.core.location import list_locations
from scene.core.scene import create_scene, delete_scene, list_scenes, update_scene
from scene.core.scene_character import assign_character, list_characters_for_scene, unassign_character
from scene.core.scene_location import assign_location, list_locations_for_scene, unassign_location
from scene.data.database import session_scope
from scene.gui.list_sizing import fit_list_height_to_contents
from scene.gui.section_heading import section_heading


class ScenesWidget(QWidget):
    """List, create, edit, and delete a story's scenes, and manage a selected scene's
    character/location assignments.

    Emits `scene_selected` whenever the selected scene changes (including to `None`).
    """

    scene_selected = Signal(object)  # int | None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.story_id: int | None = None
        self.current_scene_id: int | None = None

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_current_item_changed)

        self.heading_edit = QLineEdit()
        self.position_edit = QSpinBox()
        self.position_edit.setMaximum(9999)
        self.description_edit = QPlainTextEdit()
        self.required_actions_edit = QPlainTextEdit()
        self.length_edit = QLineEdit()

        self.new_button = QPushButton("New Scene")
        self.new_button.clicked.connect(self._on_new_clicked)

        self.save_button = QPushButton("Save Scene")
        self.save_button.clicked.connect(self._on_save_clicked)

        self.delete_button = QPushButton("Delete Scene")
        self.delete_button.clicked.connect(self._on_delete_clicked)

        form = QFormLayout()
        form.addRow("Heading", self.heading_edit)
        form.addRow("Position", self.position_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Required Actions", self.required_actions_edit)
        form.addRow("Length", self.length_edit)

        buttons = QHBoxLayout()
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.delete_button)

        self.character_list = QListWidget()
        self.character_list.itemChanged.connect(self._on_character_item_changed)

        self.location_list = QListWidget()
        self.location_list.itemChanged.connect(self._on_location_item_changed)

        layout = QVBoxLayout(self)
        layout.addWidget(section_heading("Scenes"))
        layout.addWidget(self.list_widget)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("Characters in Scene"))
        layout.addWidget(self.character_list)
        layout.addWidget(QLabel("Locations in Scene"))
        layout.addWidget(self.location_list)
        layout.addStretch()

    def load(self, story_id: int) -> None:
        self.story_id = story_id
        self.refresh()

    def refresh(self, select_scene_id: int | None = None) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        with session_scope() as session:
            for scene in list_scenes(session, self.story_id):
                label = scene.heading or scene.description
                item = QListWidgetItem(f"{scene.position}: {label}")
                item.setData(Qt.ItemDataRole.UserRole, scene.id)
                self.list_widget.addItem(item)
                if scene.id == select_scene_id:
                    self.list_widget.setCurrentItem(item)
        self.list_widget.blockSignals(False)
        fit_list_height_to_contents(self.list_widget)
        self._load_detail(select_scene_id)
        self.scene_selected.emit(select_scene_id)

    def refresh_assignment_options(self) -> None:
        """Re-populate the character/location checklists for the current scene selection.

        Called when the Characters or Locations sections change, so newly created, renamed, or
        deleted entities are reflected here without requiring the user to reselect the scene.
        """
        if self.current_scene_id is not None:
            self._load_assignments(self.current_scene_id)

    def _on_current_item_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        scene_id = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        self._load_detail(scene_id)
        self.scene_selected.emit(scene_id)

    def _load_detail(self, scene_id: int | None) -> None:
        self.current_scene_id = scene_id
        if scene_id is None:
            self.heading_edit.clear()
            self.position_edit.setValue(0)
            self.description_edit.clear()
            self.required_actions_edit.clear()
            self.length_edit.clear()
            self.character_list.clear()
            fit_list_height_to_contents(self.character_list)
            self.location_list.clear()
            fit_list_height_to_contents(self.location_list)
            return
        with session_scope() as session:
            scenes = {scene.id: scene for scene in list_scenes(session, self.story_id)}
        scene = scenes.get(scene_id)
        if scene is None:
            return
        self.heading_edit.setText(scene.heading or "")
        self.position_edit.setValue(scene.position)
        self.description_edit.setPlainText(scene.description)
        self.required_actions_edit.setPlainText(scene.required_actions or "")
        self.length_edit.setText(scene.length or "")
        self._load_assignments(scene_id)

    def _load_assignments(self, scene_id: int) -> None:
        with session_scope() as session:
            all_characters = list_characters(session, self.story_id)
            assigned_character_ids = {character.id for character in list_characters_for_scene(session, scene_id)}
            all_locations = list_locations(session, self.story_id)
            assigned_location_ids = {location.id for location in list_locations_for_scene(session, scene_id)}

        self.character_list.blockSignals(True)
        self.character_list.clear()
        for character in all_characters:
            self.character_list.addItem(
                _checkable_item(character.id, character.name, character.id in assigned_character_ids)
            )
        self.character_list.blockSignals(False)
        fit_list_height_to_contents(self.character_list)

        self.location_list.blockSignals(True)
        self.location_list.clear()
        for location in all_locations:
            self.location_list.addItem(
                _checkable_item(location.id, location.name, location.id in assigned_location_ids)
            )
        self.location_list.blockSignals(False)
        fit_list_height_to_contents(self.location_list)

    def _on_new_clicked(self) -> None:
        if self.story_id is None:
            return
        with session_scope() as session:
            position = len(list_scenes(session, self.story_id))
            scene = create_scene(session, story_id=self.story_id, position=position, description="New scene")
            scene_id = scene.id
        self.refresh(select_scene_id=scene_id)

    def _on_save_clicked(self) -> None:
        if self.current_scene_id is None:
            return
        with session_scope() as session:
            update_scene(
                session,
                self.current_scene_id,
                position=self.position_edit.value(),
                heading=self.heading_edit.text().strip(),
                description=self.description_edit.toPlainText().strip(),
                required_actions=self.required_actions_edit.toPlainText().strip(),
                length=self.length_edit.text().strip(),
            )
        self.refresh(select_scene_id=self.current_scene_id)

    def _on_delete_clicked(self) -> None:
        if self.current_scene_id is None:
            return
        if not self._confirm_delete(self.heading_edit.text() or self.description_edit.toPlainText()):
            return
        with session_scope() as session:
            delete_scene(session, self.current_scene_id)
        self.refresh()

    def _confirm_delete(self, label: str) -> bool:
        answer = QMessageBox.question(
            self,
            "Delete Scene",
            f"Delete scene '{label}'? This cannot be undone.",
        )
        return answer == QMessageBox.StandardButton.Yes

    def _on_character_item_changed(self, item: QListWidgetItem) -> None:
        if self.current_scene_id is None:
            return
        character_id = item.data(Qt.ItemDataRole.UserRole)
        checked = item.checkState() == Qt.CheckState.Checked
        with session_scope() as session:
            if checked:
                assign_character(session, self.current_scene_id, character_id)
            else:
                unassign_character(session, self.current_scene_id, character_id)

    def _on_location_item_changed(self, item: QListWidgetItem) -> None:
        if self.current_scene_id is None:
            return
        location_id = item.data(Qt.ItemDataRole.UserRole)
        checked = item.checkState() == Qt.CheckState.Checked
        with session_scope() as session:
            if checked:
                assign_location(session, self.current_scene_id, location_id)
            else:
                unassign_location(session, self.current_scene_id, location_id)


def _checkable_item(entity_id: int, name: str, checked: bool) -> QListWidgetItem:
    item = QListWidgetItem(name)
    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    item.setData(Qt.ItemDataRole.UserRole, entity_id)
    return item
