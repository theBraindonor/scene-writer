import threading
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox, QPlainTextEdit

import scene.data.database as database_module
import scene.gui.rendering_column as rendering_column_module
from scene.agent.config import LLMConfig
from scene.agent.continuity import (
    ContinuityContentDelta,
    ContinuityEvent,
    ContinuityReasoningDelta,
    ContinuitySceneComplete,
    ContinuitySceneStarted,
)
from scene.agent.rendering import RenderComplete, RenderContentDelta, RenderEvent, RenderReasoningDelta
from scene.core.continuity_snapshot import create_snapshot
from scene.core.rendering import create_rendering, list_renderings, set_active_rendering
from scene.core.scene import create_scene
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.rendering_column import (
    BODY_FONT_SCALE,
    CANCELLED_SAVED_TEXT,
    CONTINUITY_SNAPSHOT_REASONING_TAB_LABEL,
    CONTINUITY_SNAPSHOT_TAB_LABEL,
    DELETE_ACTIVE_RENDERING_TEXT,
    DELETE_SOLE_RENDERING_TEXT,
    EARLIER_SCENE_UNRENDERED_TEXT,
    GENERATE_BUTTON_WIDTH,
    GENERATION_ERROR_EMPTY_TEXT,
    GENERATION_ERROR_SAVED_TEXT,
    NO_CONTINUITY_SNAPSHOT_TEXT,
    NO_REASONING_TEXT,
    NO_RENDERINGS_TEXT,
    NO_SCENE_SELECTED_TEXT,
    PROSE_REASONING_TAB_LABEL,
    PROSE_TAB_LABEL,
    RENDER_LABEL,
    RenderingColumn,
    _format_messages,
    _PromptPreviewDialog,
)

FAKE_CONFIG = LLMConfig(model="fake-model", api_base=None, api_key=None)
FAKE_CONTINUITY_CONFIG = LLMConfig(model="fake-continuity-model", api_base=None, api_key=None)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_scene():
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A story brief")
        scene = create_scene(session, story_id=story.id, position=0, brief="Opening")
        return scene.id


def seed_scene_with_story():
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A story brief")
        scene = create_scene(session, story_id=story.id, position=0, brief="Opening")
        return story.id, scene.id


def seed_two_scene_story():
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A story brief")
        first = create_scene(session, story_id=story.id, position=0, brief="First")
        second = create_scene(session, story_id=story.id, position=1, brief="Second")
        return first.id, second.id


def test_shows_no_selection_message_by_default(qtbot):
    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)

    assert widget.stack.currentWidget() is widget.no_selection_label
    assert widget.no_selection_label.text() == NO_SCENE_SELECTED_TEXT


def test_body_view_font_is_scaled_up_from_the_default(qtbot):
    default_point_size = QPlainTextEdit().font().pointSize()

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)

    scaled_point_size = round(default_point_size * BODY_FONT_SCALE)
    assert widget.body_view.font().pointSize() == scaled_point_size
    assert widget.body_reasoning_view.font().pointSize() == scaled_point_size
    assert widget.continuity_snapshot_view.font().pointSize() == scaled_point_size
    assert widget.continuity_snapshot_reasoning_view.font().pointSize() == scaled_point_size


def test_body_view_and_continuity_snapshot_view_are_separate_tabs(qtbot):
    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)

    assert widget.tabs.count() == 4
    assert widget.tabs.tabText(0) == PROSE_TAB_LABEL
    assert widget.tabs.tabText(1) == PROSE_REASONING_TAB_LABEL
    assert widget.tabs.tabText(2) == CONTINUITY_SNAPSHOT_TAB_LABEL
    assert widget.tabs.tabText(3) == CONTINUITY_SNAPSHOT_REASONING_TAB_LABEL
    assert widget.tabs.widget(0) is widget.body_view
    assert widget.tabs.widget(1) is widget.body_reasoning_view
    assert widget.tabs.widget(2) is widget.continuity_snapshot_view
    assert widget.tabs.widget(3) is widget.continuity_snapshot_reasoning_view
    assert widget.continuity_snapshot_view.isReadOnly()
    assert widget.body_reasoning_view.isReadOnly()
    assert widget.continuity_snapshot_reasoning_view.isReadOnly()


def test_continuity_snapshot_tab_shows_placeholder_when_none_exists(qtbot):
    scene_id = seed_scene()

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert widget.continuity_snapshot_view.toPlainText() == NO_CONTINUITY_SNAPSHOT_TEXT


def test_continuity_snapshot_tab_shows_existing_snapshot(qtbot):
    story_id, scene_id = seed_scene_with_story()
    with session_scope() as session:
        create_snapshot(session, story_id, scene_id, "Mara is at the station.")

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert widget.continuity_snapshot_view.toPlainText() == "Mara is at the station."


def test_continuity_snapshot_reasoning_tab_shows_placeholder_when_no_snapshot_exists(qtbot):
    scene_id = seed_scene()

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert widget.continuity_snapshot_reasoning_view.toPlainText() == NO_CONTINUITY_SNAPSHOT_TEXT


def test_continuity_snapshot_reasoning_tab_shows_no_reasoning_fallback(qtbot):
    story_id, scene_id = seed_scene_with_story()
    with session_scope() as session:
        create_snapshot(session, story_id, scene_id, "Mara is at the station.")

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert widget.continuity_snapshot_reasoning_view.toPlainText() == NO_REASONING_TEXT


def test_continuity_snapshot_reasoning_tab_shows_captured_reasoning(qtbot):
    story_id, scene_id = seed_scene_with_story()
    with session_scope() as session:
        create_snapshot(
            session,
            story_id,
            scene_id,
            "Mara is at the station.",
            narrative_state_reasoning="Considered Mara's prior location.",
        )

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert widget.continuity_snapshot_reasoning_view.toPlainText() == "Considered Mara's prior location."


def test_shows_no_renderings_message_and_enables_generate(qtbot):
    scene_id = seed_scene()

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert widget.stack.currentWidget() is widget.content_widget
    assert widget.body_view.toPlainText() == NO_RENDERINGS_TEXT
    assert widget.body_reasoning_view.toPlainText() == NO_RENDERINGS_TEXT
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
    assert widget.body_reasoning_view.toPlainText() == NO_REASONING_TEXT
    assert widget.generate_button.text() == RENDER_LABEL


def test_version_list_shows_captured_body_reasoning(qtbot):
    scene_id = seed_scene()
    with session_scope() as session:
        rendering = create_rendering(
            session, scene_id=scene_id, body="First version.", body_reasoning="Considered the scene brief."
        )
        set_active_rendering(session, rendering.id)

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert widget.body_reasoning_view.toPlainText() == "Considered the scene brief."


def test_selecting_a_version_updates_body_view(qtbot):
    scene_id = seed_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        create_rendering(
            session, scene_id=scene_id, body="Second version.", body_reasoning="Considered continuity."
        )
        set_active_rendering(session, first.id)

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)
    assert widget.body_view.toPlainText() == "First version."
    assert widget.body_reasoning_view.toPlainText() == NO_REASONING_TEXT

    widget.version_list.setCurrentRow(1)
    assert widget.body_view.toPlainText() == "Second version."
    assert widget.body_reasoning_view.toPlainText() == "Considered continuity."


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


def _fake_accept_scene(events: list[ContinuityEvent], narrative_state: str = "Fresh state."):
    """Fakes `stream_accept_scene`: yields the given deltas, then persists and yields
    `ContinuitySceneComplete`, mirroring what the real generator does on completion."""

    def _stream(config, session, story_id, scene_id) -> Iterator[ContinuityEvent]:
        yield ContinuitySceneStarted(scene_id)
        yield from events
        snapshot = create_snapshot(session, story_id, scene_id, narrative_state)
        yield ContinuitySceneComplete(scene_id, snapshot)

    return _stream


def _fake_regenerate_snapshots(events: list[ContinuityEvent], scene_ids: list[int], narrative_state: str = "Fresh state."):
    """Fakes `stream_regenerate_snapshots_from`: yields a started/deltas/complete sequence for
    each scene id in order, mirroring the real generator's per-scene chaining."""

    def _stream(config, session, story_id, from_position) -> Iterator[ContinuityEvent]:
        for scene_id in scene_ids:
            yield ContinuitySceneStarted(scene_id)
            yield from events
            snapshot = create_snapshot(session, story_id, scene_id, narrative_state)
            yield ContinuitySceneComplete(scene_id, snapshot)

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

    with session_scope() as session:
        renderings = list_renderings(session, scene_id)
    assert len(renderings) == 1
    assert renderings[0].body == "Once upon a time."
    assert renderings[0].body_reasoning == "Thinking... "
    assert renderings[0].is_active
    assert widget.body_view.toPlainText() == "Once upon a time."
    assert widget.body_reasoning_view.toPlainText() == "Thinking... "
    assert widget.generate_button.text() == RENDER_LABEL
    assert widget.generate_button.isEnabled()


def test_generate_with_no_reasoning_deltas_saves_none_and_shows_fallback(qtbot, monkeypatch):
    scene_id = seed_scene()
    events: list[RenderEvent] = [
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

    with session_scope() as session:
        renderings = list_renderings(session, scene_id)
    assert renderings[0].body_reasoning is None
    assert widget.body_reasoning_view.toPlainText() == NO_REASONING_TEXT


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
    # `_schedule_scroll_body_to_end` defers the actual scroll via `QTimer.singleShot(0, ...)`
    # so the scrollbar's range has settled after layout; pump the event loop briefly so that
    # deferred callback runs before asserting on the scroll position.
    qtbot.wait(10)

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

    with session_scope() as session:
        assert list_renderings(session, scene_id) == []
    assert widget.notice_label.text() == GENERATION_ERROR_EMPTY_TEXT.format(error="connection reset")
    assert not widget._generating
    assert not widget.generate_button.isHidden()


def test_generate_accepts_scene_and_updates_continuity_tab(qtbot, monkeypatch):
    scene_id = seed_scene()
    events: list[RenderEvent] = [RenderContentDelta("Once upon a time."), RenderComplete("Once upon a time.")]
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream(events))

    def fake_accept_scene(config, session, story_id, accepted_scene_id):
        assert config is FAKE_CONTINUITY_CONFIG
        assert accepted_scene_id == scene_id
        yield ContinuitySceneStarted(accepted_scene_id)
        snapshot = create_snapshot(session, story_id, accepted_scene_id, "Fresh state.")
        yield ContinuitySceneComplete(accepted_scene_id, snapshot)

    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", fake_accept_scene)

    widget = RenderingColumn(FAKE_CONFIG, FAKE_CONTINUITY_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.generate_button.click()

    qtbot.waitUntil(lambda: widget.continuity_snapshot_view.toPlainText() == "Fresh state.", timeout=2000)


def test_generate_skips_accept_scene_without_continuity_config(qtbot, monkeypatch):
    scene_id = seed_scene()
    events: list[RenderEvent] = [RenderContentDelta("Once upon a time."), RenderComplete("Once upon a time.")]
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream(events))

    def unexpected_accept_scene(config, session, story_id, accepted_scene_id):
        raise AssertionError("stream_accept_scene() should not be called without a continuity_config")

    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", unexpected_accept_scene)

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.generate_button.click()

    assert widget.continuity_snapshot_view.toPlainText() == NO_CONTINUITY_SNAPSHOT_TEXT


def test_generate_shows_continuity_notice_when_accept_scene_fails(qtbot, monkeypatch):
    scene_id = seed_scene()
    events: list[RenderEvent] = [RenderContentDelta("Once upon a time."), RenderComplete("Once upon a time.")]
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream(events))

    def failing_accept_scene(config, session, story_id, accepted_scene_id):
        raise RuntimeError("boom")
        yield  # pragma: no cover - never reached; makes this a generator function

    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", failing_accept_scene)

    widget = RenderingColumn(FAKE_CONFIG, FAKE_CONTINUITY_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.generate_button.click()

    qtbot.waitUntil(lambda: "boom" in widget.continuity_notice_label.text(), timeout=2000)


def test_activate_version_calls_regenerate_snapshots_and_updates_tab(qtbot, monkeypatch):
    story_id, scene_id = seed_scene_with_story()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        create_rendering(session, scene_id=scene_id, body="Second version.")

    def fake_regenerate(config, session, regenerate_story_id, from_position):
        assert config is FAKE_CONTINUITY_CONFIG
        assert regenerate_story_id == story_id
        assert from_position == 0
        yield ContinuitySceneStarted(scene_id)
        snapshot = create_snapshot(session, regenerate_story_id, scene_id, "Fresh state.")
        yield ContinuitySceneComplete(scene_id, snapshot)

    monkeypatch.setattr(rendering_column_module, "stream_regenerate_snapshots_from", fake_regenerate)

    widget = RenderingColumn(FAKE_CONFIG, FAKE_CONTINUITY_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    widget.version_list.setCurrentRow(1)
    widget.activate_button.click()

    qtbot.waitUntil(lambda: widget.continuity_snapshot_view.toPlainText() == "Fresh state.", timeout=2000)


def test_activate_version_shows_continuity_notice_when_regenerate_fails(qtbot, monkeypatch):
    scene_id = seed_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        create_rendering(session, scene_id=scene_id, body="Second version.")

    def failing_regenerate(config, session, story_id, from_position):
        raise RuntimeError("boom")
        yield  # pragma: no cover - never reached; makes this a generator function

    monkeypatch.setattr(rendering_column_module, "stream_regenerate_snapshots_from", failing_regenerate)

    widget = RenderingColumn(FAKE_CONFIG, FAKE_CONTINUITY_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    widget.version_list.setCurrentRow(1)
    widget.activate_button.click()

    qtbot.waitUntil(lambda: "boom" in widget.continuity_notice_label.text(), timeout=2000)


def test_selecting_a_version_does_not_change_continuity_snapshot_tab(qtbot):
    story_id, scene_id = seed_scene_with_story()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        create_rendering(session, scene_id=scene_id, body="Second version.")
        set_active_rendering(session, first.id)
        create_snapshot(session, story_id, scene_id, "Stable state.")

    widget = RenderingColumn(FAKE_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)
    assert widget.continuity_snapshot_view.toPlainText() == "Stable state."

    widget.version_list.setCurrentRow(1)
    assert widget.body_view.toPlainText() == "Second version."
    assert widget.continuity_snapshot_view.toPlainText() == "Stable state."


def test_buttons_stay_blocked_while_continuity_task_runs_after_generation(qtbot, monkeypatch):
    scene_id = seed_scene()
    events: list[RenderEvent] = [RenderContentDelta("Once upon a time."), RenderComplete("Once upon a time.")]
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream(events))

    gate = threading.Event()
    accept_calls: list[int] = []

    def slow_accept_scene(config, session, story_id, accepted_scene_id):
        accept_calls.append(accepted_scene_id)
        yield ContinuitySceneStarted(accepted_scene_id)
        gate.wait(timeout=2)
        snapshot = create_snapshot(session, story_id, accepted_scene_id, "Fresh state.")
        yield ContinuitySceneComplete(accepted_scene_id, snapshot)

    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", slow_accept_scene)

    widget = RenderingColumn(FAKE_CONFIG, FAKE_CONTINUITY_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.generate_button.click()

    # The render's own worker/thread has already finished (generation_finished fired), but the
    # continuity task it kicked off is still blocked on `gate`. Generate, Activate, and Delete
    # must all stay blocked here -- otherwise a second render or Activate click could start a
    # second continuity task and clobber the still-running QThread (the crash this guard fixes).
    assert widget._continuity_busy
    assert widget.generate_button.isHidden()
    assert not widget.activate_button.isEnabled()
    assert not widget.delete_button.isEnabled()
    assert widget.progress_label.text() == "Creating continuity snapshot..."

    # The continuity worker's thread has been started but scheduling when it actually reaches
    # `accept_calls.append` is up to the OS, not this test -- wait for it rather than sampling
    # `accept_calls` at an arbitrary moment, which was flaky under load (e.g. the full suite).
    qtbot.waitUntil(lambda: accept_calls == [scene_id], timeout=2000)

    continuity_thread = widget._continuity_thread
    widget.activate_button.click()  # disabled -- must be a no-op, not a second continuity task
    assert widget._continuity_thread is continuity_thread
    assert accept_calls == [scene_id]

    gate.set()
    qtbot.waitUntil(lambda: not widget._continuity_busy, timeout=2000)

    assert not widget.generate_button.isHidden()
    assert widget.generate_button.isEnabled()
    assert widget.activate_button.isEnabled()
    assert widget.delete_button.isEnabled()
    assert widget.progress_label.text() == "Creating continuity snapshot... Done."


def test_cancel_prevents_continuity_task_from_starting(qtbot, monkeypatch):
    scene_id = seed_scene()
    gate = threading.Event()

    def _stream(config, messages) -> Iterator[RenderEvent]:
        yield RenderContentDelta("Hello ")
        gate.wait(timeout=2)
        yield RenderContentDelta("world.")
        yield RenderComplete("Hello world.")

    monkeypatch.setattr(rendering_column_module, "stream_render", _stream)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes))

    accept_calls: list[int] = []

    def tracking_accept_scene(config, session, story_id, accepted_scene_id):
        accept_calls.append(accepted_scene_id)
        yield  # pragma: no cover - never reached; this fake is only called if the guard fails

    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", tracking_accept_scene)

    widget = RenderingColumn(FAKE_CONFIG, FAKE_CONTINUITY_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    widget.generate_button.click()

    qtbot.waitUntil(lambda: widget.body_view.toPlainText() == "Hello ", timeout=2000)
    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.cancel_button.click()
        gate.set()

    assert accept_calls == []
    assert not widget._continuity_busy
    assert widget._continuity_thread is None
    assert widget.progress_label.isHidden()
    with session_scope() as session:
        renderings = list_renderings(session, scene_id)
    assert len(renderings) == 1
    assert renderings[0].body == "Hello "


def test_continuity_snapshot_tab_streams_content_and_reasoning_deltas(qtbot, monkeypatch):
    scene_id = seed_scene()
    render_events: list[RenderEvent] = [RenderContentDelta("Once upon a time."), RenderComplete("Once upon a time.")]
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream(render_events))

    gate = threading.Event()

    def gated_accept_scene(config, session, story_id, accepted_scene_id):
        yield ContinuitySceneStarted(accepted_scene_id)
        yield ContinuityReasoningDelta("Weighing ")
        yield ContinuityContentDelta("Mara is ")
        gate.wait(timeout=2)
        yield ContinuityReasoningDelta("prior events.")
        yield ContinuityContentDelta("at the station.")
        snapshot = create_snapshot(
            session,
            story_id,
            accepted_scene_id,
            "Mara is at the station.",
            narrative_state_reasoning="Weighing prior events.",
        )
        yield ContinuitySceneComplete(accepted_scene_id, snapshot)

    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", gated_accept_scene)

    widget = RenderingColumn(FAKE_CONFIG, FAKE_CONTINUITY_CONFIG)
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.generate_button.click()

    # Content and reasoning deltas both stream into the single Continuity Snapshot tab, in
    # arrival order -- mirroring how the Prose tab shows rendering's unsplit live stream --
    # and are only separated into their respective tabs once `_refresh()` re-reads the
    # persisted snapshot after the task finishes.
    qtbot.waitUntil(lambda: widget.continuity_snapshot_view.toPlainText() == "Weighing Mara is ", timeout=2000)
    assert widget.continuity_snapshot_reasoning_view.toPlainText() == NO_CONTINUITY_SNAPSHOT_TEXT

    gate.set()
    qtbot.waitUntil(lambda: not widget._continuity_busy, timeout=2000)

    assert widget.continuity_snapshot_view.toPlainText() == "Mara is at the station."
    assert widget.continuity_snapshot_reasoning_view.toPlainText() == "Weighing prior events."


def test_continuity_snapshot_tab_scrolls_to_end_as_it_streams(qtbot, monkeypatch):
    scene_id = seed_scene()
    render_events: list[RenderEvent] = [RenderContentDelta("Once upon a time."), RenderComplete("Once upon a time.")]
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream(render_events))

    long_text = "Line.\n" * 200

    def long_accept_scene(config, session, story_id, accepted_scene_id):
        yield ContinuitySceneStarted(accepted_scene_id)
        yield ContinuityContentDelta(long_text)
        snapshot = create_snapshot(session, story_id, accepted_scene_id, long_text)
        yield ContinuitySceneComplete(accepted_scene_id, snapshot)

    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", long_accept_scene)

    widget = RenderingColumn(FAKE_CONFIG, FAKE_CONTINUITY_CONFIG)
    qtbot.addWidget(widget)
    widget.resize(300, 100)
    widget.show()
    widget.set_scene(scene_id)
    # The scrollbar's range is only kept current for whatever tab is actually visible/laid
    # out, so switch to the Continuity Snapshot tab before streaming starts.
    widget.tabs.setCurrentWidget(widget.continuity_snapshot_view)

    with qtbot.waitSignal(widget.generation_finished, timeout=2000):
        widget.generate_button.click()
    qtbot.waitUntil(lambda: not widget._continuity_busy, timeout=2000)
    # `_schedule_scroll_continuity_to_end` defers the actual scroll via `QTimer.singleShot(0, ...)`
    # so the scrollbar's range has settled after layout; pump the event loop briefly so that
    # deferred callback runs before asserting on the scroll position.
    qtbot.wait(10)

    scrollbar = widget.continuity_snapshot_view.verticalScrollBar()
    assert scrollbar.value() == scrollbar.maximum()


def test_regenerate_chain_does_not_stream_other_scenes_into_visible_tab(qtbot, monkeypatch):
    story_id, first_id = seed_scene_with_story()
    with session_scope() as session:
        first_rendering = create_rendering(session, scene_id=first_id, body="First version.")
        set_active_rendering(session, first_rendering.id)
        second = create_scene(session, story_id=story_id, position=1, brief="Second")
        second_id = second.id
        second_rendering = create_rendering(session, scene_id=second_id, body="Second version.")
        set_active_rendering(session, second_rendering.id)
        create_rendering(session, scene_id=second_id, body="Second version, take two.")

    def regenerate_two_scenes(config, session, regenerate_story_id, from_position):
        yield ContinuitySceneStarted(first_id)
        yield ContinuityContentDelta("Unrelated text for the first scene.")
        first_snapshot = create_snapshot(session, regenerate_story_id, first_id, "First state.")
        yield ContinuitySceneComplete(first_id, first_snapshot)

        yield ContinuitySceneStarted(second_id)
        yield ContinuityContentDelta("Fresh state for the second scene.")
        second_snapshot = create_snapshot(session, regenerate_story_id, second_id, "Second state.")
        yield ContinuitySceneComplete(second_id, second_snapshot)

    monkeypatch.setattr(rendering_column_module, "stream_regenerate_snapshots_from", regenerate_two_scenes)

    widget = RenderingColumn(FAKE_CONFIG, FAKE_CONTINUITY_CONFIG)
    qtbot.addWidget(widget)
    # Select the second scene so the chain's first-scene deltas (`first_id`) must not appear here.
    widget.set_scene(second_id)

    widget.version_list.setCurrentRow(1)
    widget.activate_button.click()

    qtbot.waitUntil(lambda: widget.continuity_snapshot_view.toPlainText() == "Second state.", timeout=2000)
    assert "Unrelated text for the first scene." not in widget.continuity_snapshot_view.toPlainText()
