from PySide6.QtWidgets import QFormLayout, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from scene.core.story import archive_story, get_story, unarchive_story, update_story
from scene.data.database import session_scope
from scene.gui.section_heading import section_heading


class StoryDetailWidget(QWidget):
    """View/edit the selected story's title, scenario, and style guidance; archive/unarchive it."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.story_id: int | None = None
        self._is_archived = False

        self.title_edit = QLineEdit()
        self.scenario_edit = QPlainTextEdit()
        self.style_guidance_edit = QPlainTextEdit()

        self.save_button = QPushButton("Save Story")
        self.save_button.clicked.connect(self._on_save_clicked)

        self.archive_button = QPushButton("Archive")
        self.archive_button.clicked.connect(self._on_archive_clicked)

        form = QFormLayout()
        form.addRow("Title", self.title_edit)
        form.addRow("Scenario", self.scenario_edit)
        form.addRow("Style Guidance", self.style_guidance_edit)

        layout = QVBoxLayout(self)
        layout.addWidget(section_heading("Story"))
        layout.addLayout(form)
        layout.addWidget(self.save_button)
        layout.addWidget(self.archive_button)

    def load(self, story_id: int) -> None:
        self.story_id = story_id
        with session_scope() as session:
            story = get_story(session, story_id)
        if story is None:
            return
        self.title_edit.setText(story.title)
        self.scenario_edit.setPlainText(story.scenario)
        self.style_guidance_edit.setPlainText(story.style_guidance or "")
        self._is_archived = bool(story.is_archived)
        self.archive_button.setText("Unarchive" if self._is_archived else "Archive")

    def _on_save_clicked(self) -> None:
        if self.story_id is None:
            return
        with session_scope() as session:
            update_story(
                session,
                self.story_id,
                title=self.title_edit.text().strip(),
                scenario=self.scenario_edit.toPlainText().strip(),
                style_guidance=self.style_guidance_edit.toPlainText().strip(),
            )
        self.load(self.story_id)

    def _on_archive_clicked(self) -> None:
        if self.story_id is None:
            return
        with session_scope() as session:
            if self._is_archived:
                unarchive_story(session, self.story_id)
            else:
                archive_story(session, self.story_id)
        self.load(self.story_id)
