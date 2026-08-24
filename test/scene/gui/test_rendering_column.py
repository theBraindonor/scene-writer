import threading
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox, QPlainTextEdit

import scene.data.database as database_module
import scene.gui.rendering_column as rendering_column_module
from scene.agent.config import LLMConfig
from scene.agent.rendering import RenderComplete, RenderContentDelta, RenderEvent, RenderReasoningDelta
from scene.core.rendering import create_rendering, list_renderings, set_active_rendering
from scene.core.scene import create_scene
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.rendering_column import (
    BODY_FONT_SCALE,
    CANCELLED_SAVED_TEXT,
    DELETE_ACTIVE_RENDERING_TEXT,
    DELETE_SOLE_RENDERING_TEXT,
    EARLIER_SCENE_UNRENDERED_TEXT,
    GENERATE_BUTTON_WIDTH,
    GENERATION_ERROR_EMPTY_TEXT,
    GENERATION_ERROR_SAVED_TEXT,
    NO_RENDERINGS_TEXT,
    NO_SCENE_SELECTED_TEXT,
    RENDER_LABEL,
    RenderingColumn,
    _format_messages,
    _PromptPreviewDialog,
)

FAKE_CONFIG = LLMConfig(model="fake-model", api_base=None, api_key=None)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_scene():
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A story brief")
        scene = create_scene(session, story_id=story.id, position=0, brief="Opening")
        return scene.id


def seed_two_scene_story():
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A story brief")
        first = create_scene(session, story_id=story.id, position=0, brief="First")
        second = create_scene(session, story_id=story.id, position=1, brief="Second")
        return first.id, second.id


def wait_for_worker_thread_to_finish(qtbot, widget):
    # `generation_finished` only guarantees the worker's `run()` returned, not that the QThread
    # it ran on has fully unwound and its deferred `deleteLater()` cleanup has run (see
    # `_on_generation_finished`'s comment on why `_thread` is left referenced rather than
    # nulled) — pumping the event loop briefly here lets that cleanup settle before the next
    # test starts, without touching `widget._thread` itself (which may already be a dangling
    # wrapper around a deleted C++ object by this point).
    qtbot.wait(50)


def test_shows_no_selection_message_by_default(qtbot):
    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)

    assert widget.stack.currentWidget() is widget.no_selection_label
    assert widget.no_selection_label.text() == NO_SCENE_SELECTED_TEXT


def test_body_view_font_is_scaled_up_from_the_default(qtbot):
    default_point_size = QPlainTextEdit().font().pointSize()

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)

    assert widget.body_view.font().pointSize() == round(default_point_size * BODY_FONT_SCALE)


def test_shows_no_renderings_message_and_enables_generate(qtbot):
    scene_id = seed_scene()

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert widget.stack.currentWidget() is widget.content_widget
    assert widget.body_view.toPlainText() == NO_RENDERINGS_TEXT
    assert widget.version_list.count() == 0
    assert widget.generate_button.text() == RENDER_LABEL
    assert widget.generate_button.isEnabled()
    assert not widget.preview_prompt_checkbox.isChecked()


def test_version_list_shows_active_marker_and_active_body(qtbot):
    scene_id = seed_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        second = create_rendering(session, scene_id=scene_id, body="Second version.")
        set_active_rendering(session, second.id)

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert widget.version_list.count() == 2
    assert widget.version_list.item(0).text() == "○ v1"
    assert widget.version_list.item(1).text() == "● v2 (active)"
    assert widget.body_view.toPlainText() == "Second version."
    assert widget.generate_button.text() == RENDER_LABEL


def test_selecting_a_version_updates_body_view(qtbot):
    scene_id = seed_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        create_rendering(session, scene_id=scene_id, body="Second version.")
        set_active_rendering(session, first.id)

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)
    assert widget.body_view.toPlainText() == "First version."

    widget.version_list.setCurrentRow(1)
    assert widget.body_view.toPlainText() == "Second version."


def test_activate_version_makes_it_active(qtbot):
    scene_id = seed_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        create_rendering(session, scene_id=scene_id, body="Second version.")

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    widget.version_list.setCurrentRow(1)
    widget.activate_button.click()

    with session_scope() as session:
        renderings = list_renderings(session, scene_id)
    active = next(rendering for rendering in renderings if rendering.is_active)
    assert active.body == "Second version."
    assert widget.body_view.toPlainText() == "Second version."


def test_delete_blocks_sole_rendering(qtbot):
    scene_id = seed_scene()
    with session_scope() as session:
        rendering = create_rendering(session, scene_id=scene_id, body="Only version.")
        set_active_rendering(session, rendering.id)

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    widget.version_list.setCurrentRow(0)
    widget.delete_button.click()

    assert widget.notice_label.text() == DELETE_SOLE_RENDERING_TEXT
    with session_scope() as session:
        assert len(list_renderings(session, scene_id)) == 1


def test_delete_blocks_active_rendering(qtbot):
    scene_id = seed_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        create_rendering(session, scene_id=scene_id, body="Second version.")
        set_active_rendering(session, first.id)

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    widget.version_list.setCurrentRow(0)
    widget.delete_button.click()

    assert widget.notice_label.text() == DELETE_ACTIVE_RENDERING_TEXT
    with session_scope() as session:
        assert len(list_renderings(session, scene_id)) == 2


def test_delete_non_active_version_removes_it(qtbot, monkeypatch):
    scene_id = seed_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        create_rendering(session, scene_id=scene_id, body="Second version.")
        set_active_rendering(session, first.id)

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes))

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    widget.version_list.setCurrentRow(1)
    widget.delete_button.click()

    with session_scope() as session:
        remaining = list_renderings(session, scene_id)
    assert len(remaining) == 1
    assert remaining[0].body == "First version."


def test_generate_blocked_when_earlier_scene_unrendered(qtbot):
    _first_id, second_id = seed_two_scene_story()

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(second_id)

    assert not widget.generate_button.isEnabled()
    assert widget.notice_label.text() == EARLIER_SCENE_UNRENDERED_TEXT


def test_generate_disabled_without_llm_config(qtbot):
    scene_id = seed_scene()

    widget = RenderingColumn(None, error="Could not resolve the rendering agent's model: boom")
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert not widget.generate_button.isEnabled()
    assert widget.notice_label.text() == "Could not resolve the rendering agent's model: boom"


def _fake_stream(events: list[RenderEvent]):
    def _stream(config, messages) -> Iterator[RenderEvent]:
        yield from events

    return _stream


def test_generate_streams_and_creates_active_rendering(qtbot, monkeypatch):
    scene_id = seed_scene()
    events: list[RenderEvent] = [
        RenderReasoningDelta("Thinking... "),
        RenderContentDelta("Once "),
        RenderContentDelta("upon a time."),
        RenderComplete("Once upon a time."),
    ]
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream(events))

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.generate_button.click()
    wait_for_worker_thread_to_finish(qtbot, widget)

    with session_scope() as session:
        renderings = list_renderings(session, scene_id)
    assert len(renderings) == 1
    assert renderings[0].body == "Once upon a time."
    assert renderings[0].is_active
    assert widget.body_view.toPlainText() == "Once upon a time."
    assert widget.generate_button.text() == RENDER_LABEL
    assert widget.generate_button.isEnabled()


def test_body_view_scrolls_to_end_as_content_streams(qtbot, monkeypatch):
    scene_id = seed_scene()
    long_text = "Line.\n" * 200
    events: list[RenderEvent] = [RenderContentDelta(long_text), RenderComplete(long_text)]
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream(events))

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.resize(300, 100)
    widget.show()
    widget.set_scene(scene_id)

    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.generate_button.click()
    wait_for_worker_thread_to_finish(qtbot, widget)

    scrollbar = widget.body_view.verticalScrollBar()
    assert scrollbar.maximum() > 0
    assert scrollbar.value() == scrollbar.maximum()


def test_cancel_generation_saves_partial_output(qtbot, monkeypatch):
    scene_id = seed_scene()
    gate = threading.Event()

    def _stream(config, messages) -> Iterator[RenderEvent]:
        yield RenderContentDelta("Hello ")
        gate.wait(timeout=2)
        yield RenderContentDelta("world.")
        yield RenderComplete("Hello world.")

    monkeypatch.setattr(rendering_column_module, "stream_render", _stream)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes))

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    widget.generate_button.click()

    qtbot.waitUntil(lambda: widget.body_view.toPlainText() == "Hello ", timeout=2000)
    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.cancel_button.click()
        gate.set()
    wait_for_worker_thread_to_finish(qtbot, widget)

    with session_scope() as session:
        renderings = list_renderings(session, scene_id)
    assert len(renderings) == 1
    assert renderings[0].body == "Hello "
    assert widget.notice_label.text() == CANCELLED_SAVED_TEXT


def test_generate_and_cancel_buttons_have_fixed_width(qtbot):
    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)

    assert widget.generate_button.minimumWidth() == GENERATE_BUTTON_WIDTH
    assert widget.generate_button.maximumWidth() == GENERATE_BUTTON_WIDTH
    assert widget.cancel_button.minimumWidth() == GENERATE_BUTTON_WIDTH
    assert widget.cancel_button.maximumWidth() == GENERATE_BUTTON_WIDTH


def test_render_button_and_checkbox_hide_while_generating(qtbot, monkeypatch):
    scene_id = seed_scene()
    gate = threading.Event()

    def _stream(config, messages) -> Iterator[RenderEvent]:
        yield RenderContentDelta("Hello ")
        gate.wait(timeout=2)
        yield RenderComplete("Hello ")

    monkeypatch.setattr(rendering_column_module, "stream_render", _stream)

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert not widget.generate_button.isHidden()
    assert not widget.preview_prompt_checkbox.isHidden()
    assert widget.cancel_button.isHidden()

    widget.generate_button.click()
    qtbot.waitUntil(lambda: widget.body_view.toPlainText() == "Hello ", timeout=2000)

    assert widget.generate_button.isHidden()
    assert widget.preview_prompt_checkbox.isHidden()
    assert not widget.cancel_button.isHidden()

    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        gate.set()
    wait_for_worker_thread_to_finish(qtbot, widget)

    assert not widget.generate_button.isHidden()
    assert not widget.preview_prompt_checkbox.isHidden()
    assert widget.cancel_button.isHidden()


def test_format_messages_includes_role_and_content():
    formatted = _format_messages([{"role": "system", "content": "A scenario."}, {"role": "user", "content": "hi"}])

    assert "--- system ---\nA scenario." in formatted
    assert "--- user ---\nhi" in formatted


def test_preview_prompt_checked_opens_dialog_and_cancel_aborts_generation(qtbot, monkeypatch):
    scene_id = seed_scene()

    def unexpected_stream(config, messages) -> Iterator[RenderEvent]:
        raise AssertionError("stream_render() should not be called when the preview dialog is cancelled")

    monkeypatch.setattr(rendering_column_module, "stream_render", unexpected_stream)
    monkeypatch.setattr(_PromptPreviewDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)
    widget.preview_prompt_checkbox.setChecked(True)

    widget.generate_button.click()

    assert not widget._generating
    assert not widget.generate_button.isHidden()
    with session_scope() as session:
        assert list_renderings(session, scene_id) == []


def test_preview_prompt_checked_and_proceed_starts_generation(qtbot, monkeypatch):
    scene_id = seed_scene()
    events: list[RenderEvent] = [RenderContentDelta("Once upon a time."), RenderComplete("Once upon a time.")]
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream(events))
    monkeypatch.setattr(_PromptPreviewDialog, "exec", lambda self: QDialog.DialogCode.Accepted)

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)
    widget.preview_prompt_checkbox.setChecked(True)

    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.generate_button.click()
    wait_for_worker_thread_to_finish(qtbot, widget)

    with session_scope() as session:
        renderings = list_renderings(session, scene_id)
    assert len(renderings) == 1
    assert renderings[0].body == "Once upon a time."


def test_stream_error_after_partial_content_saves_and_notifies(qtbot, monkeypatch):
    scene_id = seed_scene()

    def _stream(config, messages) -> Iterator[RenderEvent]:
        yield RenderContentDelta("Once upon a time,")
        raise ConnectionError("connection reset")

    monkeypatch.setattr(rendering_column_module, "stream_render", _stream)

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.generate_button.click()
    wait_for_worker_thread_to_finish(qtbot, widget)

    with session_scope() as session:
        renderings = list_renderings(session, scene_id)
    assert len(renderings) == 1
    assert renderings[0].body == "Once upon a time,"
    assert renderings[0].is_active
    assert widget.notice_label.text() == GENERATION_ERROR_SAVED_TEXT.format(error="connection reset")
    assert not widget._generating
    assert not widget.generate_button.isHidden()
    assert widget.cancel_button.isHidden()


def test_stream_error_before_any_content_saves_nothing_and_notifies(qtbot, monkeypatch):
    scene_id = seed_scene()

    def _stream(config, messages) -> Iterator[RenderEvent]:
        raise ConnectionError("connection reset")
        yield  # pragma: no cover - makes this a generator; never reached

    monkeypatch.setattr(rendering_column_module, "stream_render", _stream)

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.generate_button.click()
    wait_for_worker_thread_to_finish(qtbot, widget)

    with session_scope() as session:
        assert list_renderings(session, scene_id) == []
    assert widget.notice_label.text() == GENERATION_ERROR_EMPTY_TEXT.format(error="connection reset")
    assert not widget._generating
    assert not widget.generate_button.isHidden()
