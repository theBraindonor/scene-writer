import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPlainTextEdit

import scene.data.database as database_module
import scene.gui.full_story_dialog as full_story_dialog_module
from scene.core.rendering import create_rendering, set_active_rendering
from scene.core.scene import create_scene
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.full_story_dialog import (
    BODY_FONT_SCALE,
    SCENE_SEPARATOR,
    FullStoryDialog,
    combine_story_prose,
    save_text_to_file,
)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_story():
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A story brief")
        return story.id


def add_rendered_scene(story_id, position, body):
    with session_scope() as session:
        scene = create_scene(session, story_id=story_id, position=position, brief="Brief")
        rendering = create_rendering(session, scene_id=scene.id, body=body)
        set_active_rendering(session, rendering.id)


def add_unrendered_scene(story_id, position):
    with session_scope() as session:
        create_scene(session, story_id=story_id, position=position, brief="Brief")


def test_combine_story_prose_joins_active_renderings_in_position_order():
    story_id = seed_story()
    add_rendered_scene(story_id, 1, "Second scene.")
    add_rendered_scene(story_id, 0, "First scene.")

    with session_scope() as session:
        text = combine_story_prose(session, story_id)

    assert text == f"First scene.{SCENE_SEPARATOR}Second scene."


def test_combine_story_prose_skips_scenes_without_an_active_rendering():
    story_id = seed_story()
    add_rendered_scene(story_id, 0, "First scene.")
    add_unrendered_scene(story_id, 1)
    add_rendered_scene(story_id, 2, "Third scene.")

    with session_scope() as session:
        text = combine_story_prose(session, story_id)

    assert text == f"First scene.{SCENE_SEPARATOR}Third scene."


def test_combine_story_prose_returns_empty_string_for_story_with_no_renderings():
    story_id = seed_story()
    add_unrendered_scene(story_id, 0)

    with session_scope() as session:
        text = combine_story_prose(session, story_id)

    assert text == ""


def test_save_text_to_file_writes_the_chosen_path(tmp_path, monkeypatch):
    target = tmp_path / "story.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target), ""))

    result = save_text_to_file(None, "Some prose.")

    assert result is True
    assert target.read_text(encoding="utf-8") == "Some prose."


def test_save_text_to_file_returns_false_without_writing_when_cancelled(tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: ("", ""))

    result = save_text_to_file(None, "Some prose.")

    assert result is False
    assert list(tmp_path.iterdir()) == []


def test_save_text_to_file_appends_txt_extension_when_missing(tmp_path, monkeypatch):
    target = tmp_path / "story"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target), ""))

    result = save_text_to_file(None, "Some prose.")

    assert result is True
    assert (tmp_path / "story.txt").read_text(encoding="utf-8") == "Some prose."


def test_save_text_to_file_shows_error_and_returns_false_on_write_failure(tmp_path, monkeypatch):
    target = tmp_path / "missing-dir" / "story.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target), ""))
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: shown.append(args[1:]))

    result = save_text_to_file(None, "Some prose.")

    assert result is False
    assert shown


def test_full_story_dialog_shows_the_given_text(qtbot):
    dialog = FullStoryDialog("Combined prose.")
    qtbot.addWidget(dialog)

    assert dialog.text_view.toPlainText() == "Combined prose."
    assert dialog.text_view.isReadOnly()


def test_full_story_dialog_scales_font_by_body_font_scale(qtbot):
    baseline = QPlainTextEdit().font().pointSize()
    dialog = FullStoryDialog("Combined prose.")
    qtbot.addWidget(dialog)

    assert dialog.text_view.font().pointSize() == round(baseline * BODY_FONT_SCALE)


def test_full_story_dialog_save_button_calls_save_text_to_file(qtbot, monkeypatch):
    calls = []
    monkeypatch.setattr(
        full_story_dialog_module, "save_text_to_file", lambda parent, text: calls.append((parent, text))
    )
    dialog = FullStoryDialog("Combined prose.")
    qtbot.addWidget(dialog)

    dialog.save_button.clicked.emit()

    assert calls == [(dialog, "Combined prose.")]


def test_full_story_dialog_close_button_accepts(qtbot):
    dialog = FullStoryDialog("Combined prose.")
    qtbot.addWidget(dialog)

    dialog.close_button.clicked.emit()

    assert dialog.result() == dialog.DialogCode.Accepted
