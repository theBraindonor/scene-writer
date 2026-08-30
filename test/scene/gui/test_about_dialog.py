from scene.gui.about_dialog import AboutDialog, _installed_version


def test_about_dialog_shows_name_and_version(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    assert dialog.title_label.text() == "Scene Writer"
    assert dialog.version_label.text() == f"Version {_installed_version()}"


def test_about_dialog_shows_a_description(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    assert "Scene Writer" in dialog.description_label.text()
    assert dialog.description_label.wordWrap()


def test_about_dialog_ok_button_accepts(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    dialog.button_box.accepted.emit()

    assert dialog.result() == dialog.DialogCode.Accepted
