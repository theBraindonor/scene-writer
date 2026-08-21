from PySide6.QtWidgets import QListWidget, QListWidgetItem

from scene.gui.list_sizing import fit_list_height_to_contents


def test_height_grows_with_item_count_up_to_cap(qtbot):
    list_widget = QListWidget()
    qtbot.addWidget(list_widget)

    fit_list_height_to_contents(list_widget, max_visible_rows=6)
    assert list_widget.height() > 0

    list_widget.addItem(QListWidgetItem("One"))
    fit_list_height_to_contents(list_widget, max_visible_rows=6)
    one_item_height = list_widget.height()

    list_widget.addItem(QListWidgetItem("Two"))
    fit_list_height_to_contents(list_widget, max_visible_rows=6)
    two_item_height = list_widget.height()
    assert two_item_height > one_item_height

    for index in range(3, 10):
        list_widget.addItem(QListWidgetItem(str(index)))
    fit_list_height_to_contents(list_widget, max_visible_rows=6)
    capped_height = list_widget.height()

    list_widget.addItem(QListWidgetItem("11"))
    fit_list_height_to_contents(list_widget, max_visible_rows=6)
    assert list_widget.height() == capped_height
