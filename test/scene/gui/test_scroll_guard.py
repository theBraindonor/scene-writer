from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from scene.gui.scroll_guard import NoScrollComboBox, NoScrollSpinBox


def _wheel_event() -> QWheelEvent:
    return QWheelEvent(
        QPoint(0, 0).toPointF(),
        QPoint(0, 0).toPointF(),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def _send_wheel_event(widget) -> None:
    # Dispatch through QApplication rather than calling wheelEvent() directly: Qt's default
    # WheelFocus policy grants focus as part of delivering a real wheel event, which would make
    # a direct wheelEvent() call miss a widget that grabs focus from the wheel event itself.
    QApplication.instance().sendEvent(widget, _wheel_event())


def test_spin_box_ignores_wheel_without_focus(qtbot):
    spin_box = NoScrollSpinBox()
    qtbot.addWidget(spin_box)
    spin_box.show()
    spin_box.setValue(5)

    _send_wheel_event(spin_box)

    assert spin_box.value() == 5
    assert not spin_box.hasFocus()


def test_spin_box_responds_to_wheel_with_focus(qtbot):
    spin_box = NoScrollSpinBox()
    qtbot.addWidget(spin_box)
    spin_box.show()
    spin_box.setValue(5)
    spin_box.setFocus()
    qtbot.waitUntil(spin_box.hasFocus)

    _send_wheel_event(spin_box)

    assert spin_box.value() != 5


def test_combo_box_ignores_wheel_without_focus(qtbot):
    combo_box = NoScrollComboBox()
    qtbot.addWidget(combo_box)
    combo_box.addItems(["One", "Two", "Three"])
    combo_box.setCurrentIndex(1)
    combo_box.show()

    _send_wheel_event(combo_box)

    assert combo_box.currentIndex() == 1
    assert not combo_box.hasFocus()


def test_combo_box_responds_to_wheel_with_focus(qtbot):
    combo_box = NoScrollComboBox()
    qtbot.addWidget(combo_box)
    combo_box.addItems(["One", "Two", "Three"])
    combo_box.setCurrentIndex(1)
    combo_box.show()
    combo_box.setFocus()
    qtbot.waitUntil(combo_box.hasFocus)

    _send_wheel_event(combo_box)

    assert combo_box.currentIndex() != 1
