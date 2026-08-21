from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QSplitter, QVBoxLayout, QWidget

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
from scene.gui.sidebar import Sidebar

SIDEBAR_PANE_INDEX = 0
DEFAULT_SIDEBAR_WIDTH = 220


class MainWindow(QMainWindow):
    """Four-region application shell: sidebar, entity column, rendering column, chat panel.

    All four regions are functional. The chat panel drives the same coordinating agent
    `scene-coordinator chat` uses, sharing one `CoordinatorState`/tool list with this window so
    direct edits and chat-driven edits stay in sync.
    """

    current_story_changed = Signal(object)  # int | None

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Scene Writer")

        self.current_story_id: int | None = None
        self._sidebar_expanded_width = DEFAULT_SIDEBAR_WIDTH

        self.sidebar = Sidebar()
        self.sidebar.story_selected.connect(self._on_story_selected)
        self.sidebar.collapse_toggled.connect(self._on_sidebar_collapse_toggled)

        self.entity_column = EntityColumn()
        self.current_story_changed.connect(self.entity_column.set_story)

        self.rendering_column = RenderingColumn()
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

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.entity_column)
        self.splitter.addWidget(self.rendering_column)

        # Sidebar's collapse toggle lives in this always-visible header, not inside the
        # splitter pane it controls — that pane's width goes to zero on collapse, which
        # would carry the button's width down with it.
        header_layout = QHBoxLayout()
        header_layout.addWidget(self.sidebar.collapse_button)
        header_layout.addStretch()

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(header_layout)
        layout.addWidget(self.splitter)
        layout.addWidget(self.chat_panel)
        self.setCentralWidget(central)

    def _on_story_selected(self, story_id: int | None) -> None:
        self.current_story_id = story_id
        self.coordinator_state.current_story_id = story_id
        self.current_story_changed.emit(story_id)

    def _on_chat_turn_completed(self) -> None:
        agent_story_id = self.coordinator_state.current_story_id
        if agent_story_id != self.current_story_id:
            # Re-populates from the database (picking up anything the agent created) and
            # selects the agent's current story, which cascades through _on_story_selected
            # into current_story_changed — refreshing the entity and rendering columns too.
            self.sidebar.refresh_stories(select_story_id=agent_story_id)
        else:
            self.entity_column.set_story(self.current_story_id)

    def _on_sidebar_collapse_toggled(self, collapsed: bool) -> None:
        sizes = self.splitter.sizes()
        if collapsed:
            if sizes[SIDEBAR_PANE_INDEX] > 0:
                self._sidebar_expanded_width = sizes[SIDEBAR_PANE_INDEX]
            sizes[SIDEBAR_PANE_INDEX] = 0
        else:
            sizes[SIDEBAR_PANE_INDEX] = self._sidebar_expanded_width
        self.splitter.setSizes(sizes)
