from scene.gui.section_heading import section_heading


def test_section_heading_is_bold_and_shows_text(qtbot):
    label = section_heading("Scenes")
    qtbot.addWidget(label)

    assert label.text() == "Scenes"
    assert label.font().bold()
