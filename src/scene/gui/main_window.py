from PySide6.QtCore import Qt, Signal
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
    """Four-region application shell: story header, entity column, rendering column, chat panel.

    All four regions are functional. The chat panel drives the same coordinating agent
    `scene-coordinator chat` uses, sharing one `CoordinatorState`/tool list with this window so
    direct edits and chat-driven edits stay in sync.
    """

    current_story_changed = Signal(object)  # int | None

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Scene Writer")

        self.current_story_id: int | None = None

        self.story_header = StoryHeader()
        self.story_header.story_selected.connect(self._on_story_selected)

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
        self.splitter.addWidget(self.entity_column)
        self.splitter.addWidget(self.rendering_column)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.story_header)
        layout.addWidget(self.splitter)
        layout.addWidget(self.chat_panel)
        self.setCentralWidget(central)

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
