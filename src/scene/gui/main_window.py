from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QSplitter, QVBoxLayout, QWidget

from scene.gui.sidebar import Sidebar

SIDEBAR_PANE_INDEX = 0
DEFAULT_SIDEBAR_WIDTH = 220


def _placeholder(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


class MainWindow(QMainWindow):
    """Four-region application shell: sidebar, entity column, rendering column, chat panel.

    Only the sidebar is functional in this encounter; the other three panes are
    placeholders that later encounters replace.
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

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(_placeholder("Entity Column"))
        self.splitter.addWidget(_placeholder("Rendering Column"))

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
