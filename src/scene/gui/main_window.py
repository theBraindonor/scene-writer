from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import QDialog, QFileDialog, QMainWindow, QMessageBox, QSplitter, QVBoxLayout, QWidget
from sqlalchemy.exc import IntegrityError

from scene.agent.application.state import ApplicationState, ApplicationTab
from scene.agent.application.tools.character import build_character_tools
from scene.agent.application.tools.location import build_location_tools
from scene.agent.application.tools.scene import build_scene_tools
from scene.agent.application.tools.story import build_story_tools
from scene.agent.config import get_llm_config
from scene.agent.prompts import load_prompts
from scene.agent.role import AgentRole
from scene.core.scene import list_scenes
from scene.data.database import session_scope
from scene.gui.about_dialog import AboutDialog
from scene.gui.chat_panel import ChatPanel
from scene.gui.entity_column.column import EntityColumn
from scene.gui.full_story_dialog import FullStoryDialog, combine_story_prose, save_text_to_file
from scene.gui.full_story_render import FullStoryRenderController, RenderFullStoryConfirmDialog
from scene.gui.rendering_column import RenderingColumn
from scene.gui.story_export import build_story_export_data, save_yaml_to_file
from scene.gui.story_header import StoryHeader
from scene.gui.story_import import DuplicateStoryTitleDialog, import_story, parse_story_import_file, story_title_exists

NO_STORY_SELECTED_TEXT = "Select a story first."
NO_SCENES_FOR_RENDER_TEXT = "This story has no scenes."
RENDERING_NOT_CONFIGURED_TEXT = "Rendering is not configured. See the Rendering panel for details."


class MainWindow(QMainWindow):
    """Application shell: a left column (story header over a draggable vertical splitter between
    the entity column and the chat panel) and a right column (rendering column), the two columns
    themselves draggable via a horizontal splitter defaulting to an even 50/50 width split.

    All regions are functional. The chat panel drives the application agent, which operates this
    window directly (opening stories, switching tabs, editing records) rather than editing rows
    blind — sharing one `ApplicationState`/tool list with this window so direct edits and
    chat-driven edits stay in sync. This is a separate agent from `scene-coordinator chat`'s
    coordinator, which the CLI still uses unchanged.
    """

    current_story_changed = Signal(object)  # int | None

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Scene Writer")

        self.current_story_id: int | None = None
        self._horizontal_manually_adjusted = False
        self._vertical_sizes_applied = False
        self._full_story_render_controller: FullStoryRenderController | None = None

        self.story_header = StoryHeader()
        self.story_header.story_selected.connect(self._on_story_selected)

        self.entity_column = EntityColumn()
        self.current_story_changed.connect(self.entity_column.set_story)

        try:
            rendering_llm_config = get_llm_config(AgentRole.RENDERING)
            rendering_llm_error = None
        except (RuntimeError, TypeError) as error:
            rendering_llm_config = None
            rendering_llm_error = f"Could not resolve the rendering agent's model: {error}"

        try:
            continuity_llm_config = get_llm_config(AgentRole.CONTINUITY_EDITING)
            continuity_llm_error = None
        except (RuntimeError, TypeError) as error:
            continuity_llm_config = None
            continuity_llm_error = f"Could not resolve the continuity-editor agent's model: {error}"

        rendering_error = rendering_llm_error
        if continuity_llm_error is not None:
            rendering_error = (
                f"{rendering_error}\n{continuity_llm_error}" if rendering_error else continuity_llm_error
            )

        self.rendering_column = RenderingColumn(
            rendering_llm_config, continuity_llm_config, error=rendering_error
        )
        self.entity_column.current_scene_changed.connect(self.rendering_column.set_scene)
        # Switching stories always resets the selected scene to None via EntityColumn's own
        # cascade, but the rendering column depends on that reset explicitly per its contract
        # rather than relying on that as an implementation detail of EntityColumn.
        self.current_story_changed.connect(lambda _story_id: self.rendering_column.set_scene(None))

        self.application_state = ApplicationState()
        self.application_tools = [
            *build_story_tools(self.application_state),
            *build_character_tools(self.application_state),
            *build_location_tools(self.application_state),
            *build_scene_tools(self.application_state),
        ]
        try:
            llm_config = get_llm_config(AgentRole.APPLICATION)
            llm_error = None
        except (RuntimeError, TypeError) as error:
            llm_config = None
            llm_error = f"Could not resolve the application agent's model: {error}"

        self.chat_panel = ChatPanel(
            llm_config,
            self.application_state,
            self.application_tools,
            system_prompt=load_prompts().application_agent_system_prompt,
            error=llm_error,
        )
        self.chat_panel.turn_completed.connect(self._on_chat_turn_completed)
        self.chat_panel.collapse_toggled.connect(self._on_chat_collapse_toggled)
        self._chat_expanded_height: int | None = None

        # A draggable divider between the entity column and the chat panel, so the developer can
        # resize the chat history's share of the left column by hand. The entity column keeps
        # stretch priority over the chat panel so it (not the chat panel) absorbs extra vertical
        # space from a window resize, matching e006/e007's "tabs are the growing element" intent —
        # but a manual drag on this handle now takes precedence over that default going forward.
        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter.addWidget(self.entity_column)
        self.vertical_splitter.addWidget(self.chat_panel)
        self.vertical_splitter.setStretchFactor(0, 1)
        self.vertical_splitter.setStretchFactor(1, 0)

        self.left_column = QWidget()
        left_layout = QVBoxLayout(self.left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.story_header, 0)
        left_layout.addWidget(self.vertical_splitter, 1)

        # A draggable divider between the left and right columns, defaulting to an even 50/50
        # width split and re-asserting that on every resize until the developer drags the handle
        # themselves (tracked via splitterMoved, which only fires for a real drag — see
        # resizeEvent) — from that point on, Qt's own splitter resize behavior takes over,
        # preserving whatever ratio the developer chose instead of this window overriding it.
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.left_column)
        self.splitter.addWidget(self.rendering_column)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.splitterMoved.connect(self._on_horizontal_splitter_moved)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.splitter)
        self.setCentralWidget(central)

        self._build_menu_bar()

    def _build_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        new_action = file_menu.addAction("&New Story...")
        new_action.triggered.connect(self.story_header.new_story_button.click)
        open_action = file_menu.addAction("&Open Story...")
        open_action.triggered.connect(self.story_header.open_button.click)
        file_menu.addSeparator()
        export_action = file_menu.addAction("&Export Story...")
        export_action.triggered.connect(self._on_export_story)
        import_action = file_menu.addAction("&Import Story...")
        import_action.triggered.connect(self._on_import_story)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        render_menu = self.menuBar().addMenu("&Render")
        self.render_full_story_action = render_menu.addAction("&Render Full Story...")
        self.render_full_story_action.triggered.connect(self._on_render_full_story)
        view_full_story_action = render_menu.addAction("&View Full Story...")
        view_full_story_action.triggered.connect(self._on_view_full_story)
        save_full_story_action = render_menu.addAction("&Save Full Story...")
        save_full_story_action.triggered.connect(self._on_save_full_story)

        help_menu = self.menuBar().addMenu("&Help")
        about_action = help_menu.addAction("&About Scene Writer")
        about_action.triggered.connect(self._on_about)

    def _on_render_full_story(self) -> None:
        if self.current_story_id is None:
            QMessageBox.information(self, "Render Full Story", NO_STORY_SELECTED_TEXT)
            return
        with session_scope() as session:
            has_scenes = bool(list_scenes(session, self.current_story_id))
        if not has_scenes:
            QMessageBox.information(self, "Render Full Story", NO_SCENES_FOR_RENDER_TEXT)
            return
        if self.rendering_column._llm_config is None:
            QMessageBox.information(self, "Render Full Story", RENDERING_NOT_CONFIGURED_TEXT)
            return
        dialog = RenderFullStoryConfirmDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.render_full_story_action.setEnabled(False)
        controller = FullStoryRenderController(self)
        controller.finished.connect(self._on_full_story_render_finished)
        self._full_story_render_controller = controller
        controller.start(self.current_story_id)

    def _on_full_story_render_finished(self) -> None:
        self._full_story_render_controller = None
        self.render_full_story_action.setEnabled(True)

    def _on_view_full_story(self) -> None:
        if self.current_story_id is None:
            QMessageBox.information(self, "View Full Story", NO_STORY_SELECTED_TEXT)
            return
        with session_scope() as session:
            text = combine_story_prose(session, self.current_story_id)
        FullStoryDialog(text, self).exec()

    def _on_save_full_story(self) -> None:
        if self.current_story_id is None:
            QMessageBox.information(self, "Save Full Story", NO_STORY_SELECTED_TEXT)
            return
        with session_scope() as session:
            text = combine_story_prose(session, self.current_story_id)
        save_text_to_file(self, text)

    def _on_export_story(self) -> None:
        if self.current_story_id is None:
            QMessageBox.information(self, "Export Story", NO_STORY_SELECTED_TEXT)
            return
        with session_scope() as session:
            data = build_story_export_data(session, self.current_story_id)
        save_yaml_to_file(self, data)

    def _on_import_story(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Story", "", "YAML Files (*.yaml *.yml);;All Files (*)")
        if not path:
            return
        try:
            data = parse_story_import_file(path)
        except ValueError as error:
            QMessageBox.critical(self, "Import Story", str(error))
            return

        title = self._resolve_import_title(data["story"]["title"])
        if title is None:
            return

        with session_scope() as session:
            try:
                story_id = import_story(session, data, title)
            except (ValueError, IntegrityError) as error:
                QMessageBox.critical(self, "Import Story", f"Could not import the story: {error}")
                return

        self._on_story_selected(story_id)

    def _resolve_import_title(self, title: str) -> str | None:
        while True:
            with session_scope() as session:
                taken = story_title_exists(session, title)
            if not taken:
                return title
            dialog = DuplicateStoryTitleDialog(title, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None
            title = dialog.new_title()

    def _on_about(self) -> None:
        AboutDialog(self).exec()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._apply_even_horizontal_split()
        self._apply_default_vertical_split()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not self._horizontal_manually_adjusted:
            self._apply_even_horizontal_split()

    def _apply_even_horizontal_split(self) -> None:
        # setSizes([1, 1]) is swallowed by the panes' own sizeHint-based weighting instead of
        # producing an even split, so the actual pixel halves are computed and passed instead.
        width = self.splitter.width()
        if width > 0:
            self.splitter.setSizes([width // 2, width - width // 2])

    def _apply_default_vertical_split(self) -> None:
        # Only applied once, the first time the window has real geometry (a window isn't shown
        # with valid sizes yet at construction time) — after that, the vertical splitter's
        # stretch factors (entity column 1, chat panel 0) alone already keep the chat panel
        # pinned at whatever height it currently is, default or dragged, as the window resizes.
        if self._vertical_sizes_applied:
            return
        height = self.vertical_splitter.height()
        if height <= 0:
            return
        self._vertical_sizes_applied = True
        chat_height = self.chat_panel.sizeHint().height()
        self.vertical_splitter.setSizes([max(height - chat_height, 0), chat_height])

    def _on_horizontal_splitter_moved(self, pos: int, index: int) -> None:
        self._horizontal_manually_adjusted = True

    def _on_chat_collapse_toggled(self, expanded: bool) -> None:
        # ChatPanel.setVisible()-ing its own content shrinks its *sizeHint*, but a QSplitter
        # doesn't automatically shrink a pane to match a shrunken sizeHint on its own — its sizes
        # are pixel-fixed until told otherwise. So the vertical splitter has to be resized
        # explicitly here: reclaiming the chat panel's space for the entity column on collapse,
        # and restoring the chat panel's pre-collapse height on expand.
        total = sum(self.vertical_splitter.sizes())
        if not expanded:
            self._chat_expanded_height = self.chat_panel.height()
            chat_height = self.chat_panel.sizeHint().height()
        else:
            chat_height = self._chat_expanded_height or self.chat_panel.sizeHint().height()
        self.vertical_splitter.setSizes([max(total - chat_height, 0), chat_height])

    def _on_story_selected(self, story_id: int | None) -> None:
        self.current_story_id = story_id
        self.application_state.current_story_id = story_id
        self.application_state.current_scene_id = None
        self.story_header.set_current_story(story_id)
        self.current_story_changed.emit(story_id)

    def _on_chat_turn_completed(self) -> None:
        agent_story_id = self.application_state.current_story_id
        if agent_story_id != self.current_story_id:
            self._on_story_selected(agent_story_id)
        else:
            self.entity_column.set_story(self.current_story_id)
        self._sync_entity_column_tab()

    def _sync_entity_column_tab(self) -> None:
        # Scene selection is application state read by later turns (unlike the
        # fire-and-forget Characters/Locations selection below), so it's kept in sync with
        # the Scenes widget every turn regardless of which tab is currently visible --
        # otherwise `entity_column.set_story()` above would have already silently cleared
        # it as a side effect of reloading the Scenes list.
        if self.current_story_id is not None:
            self.entity_column.refresh_scene_selection(self.application_state.current_scene_id)

        tab = self.application_state.current_tab
        if tab is ApplicationTab.STORY:
            self.entity_column.show_story_tab()
        elif tab is ApplicationTab.CHARACTERS:
            self.entity_column.show_characters_tab(self.application_state.current_character_id)
        elif tab is ApplicationTab.LOCATIONS:
            self.entity_column.show_locations_tab(self.application_state.current_location_id)
        elif tab is ApplicationTab.SCENES:
            self.entity_column.show_scenes_tab()
