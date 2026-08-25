from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import QMainWindow, QSplitter, QVBoxLayout, QWidget

from scene.agent.config import get_llm_config
from scene.agent.coordinator.state import CoordinatorState
from scene.agent.coordinator.tools.character import build_character_tools
from scene.agent.coordinator.tools.location import build_location_tools
from scene.agent.coordinator.tools.scene import build_scene_tools
from scene.agent.coordinator.tools.story import build_story_tools
from scene.agent.role import AgentRole
from scene.gui.chat_panel import ChatPanel
from scene.gui.entity_column.column import EntityColumn
from scene.gui.rendering_column import RenderingColumn
from scene.gui.story_header import StoryHeader


class MainWindow(QMainWindow):
    """Application shell: a left column (story header over a draggable vertical splitter between
    the entity column and the chat panel) and a right column (rendering column), the two columns
    themselves draggable via a horizontal splitter defaulting to an even 50/50 width split.

    All regions are functional. The chat panel drives the same coordinating agent
    `scene-coordinator chat` uses, sharing one `CoordinatorState`/tool list with this window so
    direct edits and chat-driven edits stay in sync.
    """

    current_story_changed = Signal(object)  # int | None

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Scene Writer")

        self.current_story_id: int | None = None
        self._horizontal_manually_adjusted = False
        self._vertical_sizes_applied = False

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

        self.coordinator_state = CoordinatorState()
        self.coordinator_tools = [
            *build_story_tools(self.coordinator_state),
            *build_scene_tools(self.coordinator_state),
            *build_character_tools(self.coordinator_state),
            *build_location_tools(self.coordinator_state),
        ]
        try:
            llm_config = get_llm_config(AgentRole.COORDINATING)
            llm_error = None
        except (RuntimeError, TypeError) as error:
            llm_config = None
            llm_error = f"Could not resolve the coordinating agent's model: {error}"

        self.chat_panel = ChatPanel(llm_config, self.coordinator_state, self.coordinator_tools, error=llm_error)
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
        self.coordinator_state.current_story_id = story_id
        self.story_header.set_current_story(story_id)
        self.current_story_changed.emit(story_id)

    def _on_chat_turn_completed(self) -> None:
        agent_story_id = self.coordinator_state.current_story_id
        if agent_story_id != self.current_story_id:
            self._on_story_selected(agent_story_id)
        else:
            self.entity_column.set_story(self.current_story_id)
