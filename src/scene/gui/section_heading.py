from PySide6.QtWidgets import QLabel


def section_heading(text: str) -> QLabel:
    """A bold label identifying an entity-column section (e.g. "Scenes", "Characters")."""
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    font.setPointSize(font.pointSize() + 2)
    label.setFont(font)
    return label
