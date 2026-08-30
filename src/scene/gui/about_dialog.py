from importlib.metadata import PackageNotFoundError, version

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

DESCRIPTION_TEXT = (
    "Scene Writer is an agentic, AI-assisted scene-writing tool built around a two-phase "
    "generation pipeline: Scene Construction establishes a scene's details before any prose "
    "is generated, then Scene Drafting incrementally builds its prose using those details "
    "together with previously generated scenes for continuity."
)


def _installed_version() -> str:
    try:
        return version("scene-writer")
    except PackageNotFoundError:
        return "development"


class AboutDialog(QDialog):
    """Modal "About" dialog shown from Help > About: application name, version, and a short
    description of what Scene Writer does."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About Scene Writer")
        self.setModal(True)

        self.title_label = QLabel("Scene Writer")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14pt;")

        self.version_label = QLabel(f"Version {_installed_version()}")

        self.description_label = QLabel(DESCRIPTION_TEXT)
        self.description_label.setWordWrap(True)
        self.description_label.setMaximumWidth(360)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.button_box.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.version_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.description_label)
        layout.addWidget(self.button_box)
