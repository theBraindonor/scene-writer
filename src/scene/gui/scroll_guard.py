from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QComboBox, QSpinBox, QWidget


class NoScrollSpinBox(QSpinBox):
    """A QSpinBox that only responds to the mouse wheel once it already has focus, so scrolling
    the page past it doesn't silently change its value."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # The base class's default WheelFocus policy grants focus as part of delivering the
        # wheel event itself, which would make hasFocus() below always true. Dropping to
        # StrongFocus keeps click/tab focus but stops the wheel from granting it.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class NoScrollComboBox(QComboBox):
    """A QComboBox that only responds to the mouse wheel once it already has focus, so scrolling
    the page past it doesn't silently change its selection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()
