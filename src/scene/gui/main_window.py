from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QSplitter, QVBoxLayout, QWidget

from scene.gui.entity_column.column import EntityColumn
from scene.gui.rendering_column import RenderingColumn
from scene.gui.sidebar import Sidebar

SIDEBAR_PANE_INDEX = 0
DEFAULT_SIDEBAR_WIDTH = 220


def _placeholder(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


class MainWindow(QMainWindow):
    """Four-region application shell: sidebar, entity column, rendering column, chat panel.

    The sidebar, entity column, and rendering column are functional; the chat panel remains a
    placeholder that a later encounter replaces.
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
        layout.addWidget(_placeholder("Chat Panel"))
        self.setCentralWidget(central)

    def _on_story_selected(self, story_id: int | None) -> None:
        self.current_story_id = story_id
        self.current_story_changed.emit(story_id)

    def _on_sidebar_collapse_toggled(self, collapsed: bool) -> None:
        sizes = self.splitter.sizes()
        if collapsed:
            if sizes[SIDEBAR_PANE_INDEX] > 0:
                self._sidebar_expanded_width = sizes[SIDEBAR_PANE_INDEX]
            sizes[SIDEBAR_PANE_INDEX] = 0
        else:
            sizes[SIDEBAR_PANE_INDEX] = self._sidebar_expanded_width
        self.splitter.setSizes(sizes)
