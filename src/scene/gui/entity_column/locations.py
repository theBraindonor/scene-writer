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

from scene.core.location import create_location, delete_location, list_locations, update_location
from scene.data.database import session_scope
from scene.gui.list_sizing import fit_list_height_to_contents
from scene.gui.section_heading import section_heading


class LocationsWidget(QWidget):
    """List, create, edit, and delete a story's locations.

    Emits `locations_changed` after every list refresh so the Scenes section can keep its
    location-assignment checklist in sync without polling.
    """

    locations_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.story_id: int | None = None
        self.current_location_id: int | None = None

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_current_item_changed)

        self.name_edit = QLineEdit()
        self.description_edit = QPlainTextEdit()

        self.new_button = QPushButton("New Location")
        self.new_button.clicked.connect(self._on_new_clicked)

        self.save_button = QPushButton("Save Location")
        self.save_button.clicked.connect(self._on_save_clicked)

        self.delete_button = QPushButton("Delete Location")
        self.delete_button.clicked.connect(self._on_delete_clicked)

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Description", self.description_edit)

        buttons = QHBoxLayout()
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.delete_button)

        layout = QVBoxLayout(self)
        layout.addWidget(section_heading("Locations"))
        layout.addWidget(self.list_widget)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def load(self, story_id: int) -> None:
        self.story_id = story_id
        self.refresh()

    def refresh(self, select_location_id: int | None = None) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        with session_scope() as session:
            for location in list_locations(session, self.story_id):
                item = QListWidgetItem(location.name)
                item.setData(Qt.ItemDataRole.UserRole, location.id)
                self.list_widget.addItem(item)
                if location.id == select_location_id:
                    self.list_widget.setCurrentItem(item)
        self.list_widget.blockSignals(False)
        fit_list_height_to_contents(self.list_widget)
        self._load_detail(select_location_id)
        self.locations_changed.emit()

    def _on_current_item_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        location_id = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        self._load_detail(location_id)

    def _load_detail(self, location_id: int | None) -> None:
        self.current_location_id = location_id
        if location_id is None:
            self.name_edit.clear()
            self.description_edit.clear()
            return
        with session_scope() as session:
            locations = {location.id: location for location in list_locations(session, self.story_id)}
        location = locations.get(location_id)
        if location is None:
            return
        self.name_edit.setText(location.name)
        self.description_edit.setPlainText(location.description or "")

    def _on_new_clicked(self) -> None:
        if self.story_id is None:
            return
        with session_scope() as session:
            location = create_location(session, story_id=self.story_id, name="New Location")
            location_id = location.id
        self.refresh(select_location_id=location_id)

    def _on_save_clicked(self) -> None:
        if self.current_location_id is None:
            return
        with session_scope() as session:
            update_location(
                session,
                self.current_location_id,
                name=self.name_edit.text().strip(),
                description=self.description_edit.toPlainText().strip(),
            )
        self.refresh(select_location_id=self.current_location_id)

    def _on_delete_clicked(self) -> None:
        if self.current_location_id is None:
            return
        if not self._confirm_delete(self.name_edit.text()):
            return
        with session_scope() as session:
            delete_location(session, self.current_location_id)
        self.refresh()

    def _confirm_delete(self, name: str) -> bool:
        answer = QMessageBox.question(
            self,
            "Delete Location",
            f"Delete location '{name}'? This cannot be undone.",
        )
        return answer == QMessageBox.StandardButton.Yes
