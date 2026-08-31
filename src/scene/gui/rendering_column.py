from collections.abc import Callable, Iterator

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from scene.agent.config import LLMConfig
from scene.agent.continuity import (
    ContinuityContentDelta,
    ContinuityEvent,
    ContinuityReasoningDelta,
    ContinuitySceneStarted,
    stream_accept_scene,
    stream_regenerate_snapshots_from,
)
from scene.agent.rendering import (
    RenderComplete,
    RenderContentDelta,
    RenderEvent,
    RenderReasoningDelta,
    build_render_messages,
    earlier_scenes_rendered,
    stream_render,
)
from scene.core.continuity_snapshot import get_snapshot
from scene.core.rendering import (
    create_rendering,
    delete_rendering,
    get_rendering,
    list_renderings,
    set_active_rendering,
)
from scene.core.scene import get_scene
from scene.data.database import session_scope
from scene.gui.list_sizing import fit_list_height_to_contents
from scene.gui.section_heading import section_heading

NO_SCENE_SELECTED_TEXT = "Select a scene to see its rendering."
NO_RENDERINGS_TEXT = "This scene has no renderings yet."
NO_CONTINUITY_SNAPSHOT_TEXT = "(No continuity snapshot yet.)"
EARLIER_SCENE_UNRENDERED_TEXT = "An earlier scene has no active rendering yet. Render it first."
DELETE_SOLE_RENDERING_TEXT = "Cannot delete a scene's only rendering."
DELETE_ACTIVE_RENDERING_TEXT = "Cannot delete the active rendering. Activate a different version first."
CANCEL_CONFIRM_TEXT = "Cancel this generation? Any partial text will be saved as a new version."
CANCELLED_SAVED_TEXT = "Generation cancelled. Partial rendering saved as a new version."
CANCELLED_EMPTY_TEXT = "Generation cancelled. Nothing had been generated yet."
GENERATION_ERROR_SAVED_TEXT = "Generation error: {error}. Partial rendering saved as a new version."
GENERATION_ERROR_EMPTY_TEXT = "Generation error: {error}. Nothing had been generated yet."
CONTINUITY_UPDATE_FAILED_TEXT = "Continuity snapshot update failed: {error}"
CONTINUITY_REGENERATE_FAILED_TEXT = "Continuity snapshot regeneration failed: {error}"
PROSE_TAB_LABEL = "Prose"
PROSE_REASONING_TAB_LABEL = "Prose Reasoning"
CONTINUITY_SNAPSHOT_TAB_LABEL = "Continuity Snapshot"
CONTINUITY_SNAPSHOT_REASONING_TAB_LABEL = "Continuity Snapshot Reasoning"
NO_REASONING_TEXT = "The model used did not support a reasoning output."
RENDER_LABEL = "Render"
PREVIEW_PROMPT_LABEL = "Preview Prompt"
BODY_FONT_SCALE = 1.5
GENERATE_BUTTON_WIDTH = 120


class _RenderWorker(QObject):
    """Streams one `stream_render` call to completion on a background thread.

    The Qt equivalent of `RenderApp`'s `@work(thread=True)` + `call_from_thread` pattern,
    matching `ChatPanel`'s `_TurnWorker`: each yielded `RenderEvent` is forwarded via
    `event_received`, a queued-connection signal, so the main thread applies it safely.
    """

    event_received = Signal(object)  # RenderEvent
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, config: LLMConfig, messages: list[dict], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._messages = messages
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        # A dropped connection or malformed final chunk from the LLM backend must not silently
        # kill this thread without emitting `finished` — that would leave whatever text had
        # already streamed in un-saved and the column stuck showing the Cancel button forever.
        # Catching broadly here and always emitting `finished` guarantees the same
        # save-whatever-we-have path (see `RenderingColumn._on_generation_finished`) runs for a
        # stream error exactly as it does for a manual cancel or a clean finish.
        try:
            for event in stream_render(self._config, self._messages):
                if self._cancelled:
                    break
                self.event_received.emit(event)
                if isinstance(event, RenderComplete):
                    break
        except Exception as error:  # noqa: BLE001 - surfaced to the UI, never swallowed
            self.error_occurred.emit(str(error))
        self.finished.emit()


class _ContinuityWorker(QObject):
    """Streams one continuity-editor call (`stream_accept_scene` or
    `stream_regenerate_snapshots_from`) to completion on a background thread, mirroring
    `_RenderWorker`'s thread/signal pattern for the main render stream so a continuity-editor
    call (potentially several LLM round trips for a `stream_regenerate_snapshots_from` chain)
    never blocks the GUI thread."""

    event_received = Signal(object)  # ContinuityEvent
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, events_factory: Callable[[], Iterator[ContinuityEvent]], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._events_factory = events_factory

    def run(self) -> None:
        try:
            for event in self._events_factory():
                self.event_received.emit(event)
        except Exception as error:  # noqa: BLE001 - surfaced to the UI, never swallowed
            self.error_occurred.emit(str(error))
        self.finished.emit()


def _format_messages(messages: list[dict]) -> str:
    return "\n\n".join(
        f"--- {message.get('role', '')} ---\n{message.get('content', '')}" for message in messages
    )


class _PromptPreviewDialog(QDialog):
    """Shows the exact messages `build_render_messages` assembled for this generation, so the
    developer can verify multi-scene continuity context before committing to a render."""

    def __init__(self, messages: list[dict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preview Prompt")
        self.setModal(True)
        self.resize(700, 500)

        text_view = QPlainTextEdit()
        text_view.setReadOnly(True)
        text_view.setPlainText(_format_messages(messages))

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        self.proceed_button = QPushButton("Proceed")
        self.proceed_button.clicked.connect(self.accept)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.proceed_button)

        layout = QVBoxLayout(self)
        layout.addWidget(text_view)
        layout.addLayout(button_row)


class RenderingColumn(QWidget):
    """Create, browse, activate, and delete a scene's renderings, and generate new ones.

    Connects to `MainWindow.current_story_changed` and `EntityColumn.current_scene_changed` —
    switching stories resets the selected scene to `None`, so both signals drive the same
    `set_scene` reset. Mirrors the `RenderApp` Textual TUI's rendering workflow
    (`src/scene/cli/render_app.py`), the reference implementation this column ports into Qt.

    Emits `generation_finished` after every completed (or cancelled) generation, mirroring
    `ChatPanel.turn_completed`.
    """

    generation_finished = Signal()
    scene_settled = Signal()

    def __init__(
        self,
        llm_config: LLMConfig | None,
        continuity_config: LLMConfig | None = None,
        error: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._llm_config = llm_config
        self._continuity_config = continuity_config
        self.current_scene_id: int | None = None
        self.current_story_id: int | None = None
        self.current_scene_position: int | None = None
        self.selected_rendering_id: int | None = None
        self._thread: QThread | None = None
        self._worker: _RenderWorker | None = None
        self._continuity_thread: QThread | None = None
        self._continuity_worker: _ContinuityWorker | None = None
        self._generating = False
        self._continuity_busy = False
        self._generating_scene_id: int | None = None
        self._content_text = ""
        self._reasoning_text = ""
        self._display_text = ""
        self._cancel_requested = False
        self._error_message: str | None = None
        self._continuity_display_text = ""
        self._continuity_display_scene_id: int | None = None
        self.last_generation_cancelled = False
        self.last_generation_error: str | None = None
        self.last_generation_body = ""
        self.last_continuity_error: str | None = None

        self.no_selection_label = QLabel(NO_SCENE_SELECTED_TEXT)
        self.no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_selection_label.setWordWrap(True)

        self.version_list = QListWidget()
        self.version_list.currentItemChanged.connect(self._on_version_selected)

        self.body_view = QPlainTextEdit()
        self.body_view.setReadOnly(True)
        body_font = self.body_view.font()
        body_font.setPointSize(round(body_font.pointSize() * BODY_FONT_SCALE))
        self.body_view.setFont(body_font)

        self.body_reasoning_view = QPlainTextEdit()
        self.body_reasoning_view.setReadOnly(True)
        self.body_reasoning_view.setFont(body_font)

        self.continuity_snapshot_view = QPlainTextEdit()
        self.continuity_snapshot_view.setReadOnly(True)
        self.continuity_snapshot_view.setFont(body_font)

        self.continuity_snapshot_reasoning_view = QPlainTextEdit()
        self.continuity_snapshot_reasoning_view.setReadOnly(True)
        self.continuity_snapshot_reasoning_view.setFont(body_font)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.body_view, PROSE_TAB_LABEL)
        self.tabs.addTab(self.body_reasoning_view, PROSE_REASONING_TAB_LABEL)
        self.tabs.addTab(self.continuity_snapshot_view, CONTINUITY_SNAPSHOT_TAB_LABEL)
        self.tabs.addTab(self.continuity_snapshot_reasoning_view, CONTINUITY_SNAPSHOT_REASONING_TAB_LABEL)

        self.notice_label = QLabel()
        self.notice_label.setWordWrap(True)
        self.notice_label.hide()

        self.continuity_notice_label = QLabel()
        self.continuity_notice_label.setWordWrap(True)
        self.continuity_notice_label.hide()

        self.preview_prompt_checkbox = QCheckBox(PREVIEW_PROMPT_LABEL)
        self.preview_prompt_checkbox.setChecked(False)

        self.generate_button = QPushButton(RENDER_LABEL)
        self.generate_button.setFixedWidth(GENERATE_BUTTON_WIDTH)
        self.generate_button.clicked.connect(self._on_generate_clicked)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedWidth(GENERATE_BUTTON_WIDTH)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        self.cancel_button.hide()

        self.activate_button = QPushButton("Activate Version")
        self.activate_button.clicked.connect(self._on_activate_clicked)

        self.delete_button = QPushButton("Delete Version")
        self.delete_button.clicked.connect(self._on_delete_clicked)

        self.progress_label = QLabel()
        self.progress_label.hide()

        generate_row = QHBoxLayout()
        generate_row.addWidget(self.progress_label)
        generate_row.addStretch()
        generate_row.addWidget(self.preview_prompt_checkbox)
        generate_row.addWidget(self.generate_button)
        generate_row.addWidget(self.cancel_button)

        version_row = QHBoxLayout()
        version_row.addWidget(self.activate_button)
        version_row.addWidget(self.delete_button)

        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(QLabel("Versions"))
        content_layout.addWidget(self.version_list)
        content_layout.addLayout(version_row)
        content_layout.addWidget(self.tabs)
        content_layout.addLayout(generate_row)
        content_layout.addWidget(self.continuity_notice_label)
        content_layout.addWidget(self.notice_label)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.no_selection_label)
        self.stack.addWidget(self.content_widget)

        layout = QVBoxLayout(self)
        layout.addWidget(section_heading("Rendering"))
        layout.addWidget(self.stack)

        if error is not None:
            self._show_notice(error)
        if llm_config is None:
            # Only the rendering model is required to disable generation entirely -- a missing
            # continuity_config is folded into the same notice above, but stays optional
            # (mirroring e009/e011's CLI behavior), so it never blocks rendering on its own.
            self.generate_button.setEnabled(False)

    # -- scene selection ---------------------------------------------------

    def set_scene(self, scene_id: int | None) -> None:
        self.current_scene_id = scene_id
        if scene_id is None:
            self.current_story_id = None
            self.current_scene_position = None
            self.stack.setCurrentWidget(self.no_selection_label)
            return
        with session_scope() as session:
            scene = get_scene(session, scene_id)
        if scene is None:
            self.current_story_id = None
            self.current_scene_position = None
        else:
            self.current_story_id = scene.story_id
            self.current_scene_position = scene.position
        self.stack.setCurrentWidget(self.content_widget)
        self._refresh()

    # -- refresh -------------------------------------------------------------

    def _refresh(self, select_rendering_id: int | None = None) -> None:
        if self.current_scene_id is None:
            return
        with session_scope() as session:
            renderings = list_renderings(session, self.current_scene_id)
            earlier_rendered = True
            if self.current_story_id is not None and self.current_scene_position is not None:
                earlier_rendered = earlier_scenes_rendered(
                    session, self.current_story_id, self.current_scene_position
                )

        busy = self._generating or self._continuity_busy
        if busy:
            self.generate_button.hide()
            self.preview_prompt_checkbox.hide()
            self.cancel_button.show()
        else:
            self.cancel_button.hide()
            self.generate_button.show()
            self.preview_prompt_checkbox.show()
            if self._llm_config is None:
                self.generate_button.setEnabled(False)
            elif not earlier_rendered:
                self.generate_button.setEnabled(False)
                self._show_notice(EARLIER_SCENE_UNRENDERED_TEXT)
            else:
                self.generate_button.setEnabled(True)
                self._hide_notice()

        target_id = select_rendering_id
        if target_id is None:
            active = next((rendering for rendering in renderings if rendering.is_active), None)
            target_id = active.id if active is not None else (renderings[-1].id if renderings else None)

        self.version_list.blockSignals(True)
        self.version_list.clear()
        for index, rendering in enumerate(renderings, start=1):
            marker = "●" if rendering.is_active else "○"
            suffix = " (active)" if rendering.is_active else ""
            item = QListWidgetItem(f"{marker} v{index}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, rendering.id)
            self.version_list.addItem(item)
            if rendering.id == target_id:
                self.version_list.setCurrentItem(item)
        self.version_list.blockSignals(False)
        fit_list_height_to_contents(self.version_list)

        self.selected_rendering_id = target_id
        if not renderings:
            self.body_view.setPlainText(NO_RENDERINGS_TEXT)
            self.body_reasoning_view.setPlainText(NO_RENDERINGS_TEXT)
        else:
            selected = next((rendering for rendering in renderings if rendering.id == target_id), None)
            self.body_view.setPlainText(selected.body if selected is not None else "")
            self.body_reasoning_view.setPlainText(
                (selected.body_reasoning or NO_REASONING_TEXT) if selected is not None else ""
            )

        self.activate_button.setEnabled(target_id is not None and not busy)
        self.delete_button.setEnabled(target_id is not None and not busy)

        self._refresh_continuity_snapshot()

    def _refresh_continuity_snapshot(self) -> None:
        if self.current_scene_id is None or self.current_story_id is None:
            self.continuity_snapshot_view.setPlainText("")
            self.continuity_snapshot_reasoning_view.setPlainText("")
            return
        with session_scope() as session:
            snapshot = get_snapshot(session, self.current_story_id, self.current_scene_id)
        self.continuity_snapshot_view.setPlainText(
            snapshot.narrative_state if snapshot is not None else NO_CONTINUITY_SNAPSHOT_TEXT
        )
        if snapshot is not None:
            self.continuity_snapshot_reasoning_view.setPlainText(
                snapshot.narrative_state_reasoning or NO_REASONING_TEXT
            )
        else:
            self.continuity_snapshot_reasoning_view.setPlainText(NO_CONTINUITY_SNAPSHOT_TEXT)

    def _on_version_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is None:
            self.selected_rendering_id = None
            return
        rendering_id = current.data(Qt.ItemDataRole.UserRole)
        self.selected_rendering_id = rendering_id
        with session_scope() as session:
            rendering = get_rendering(session, rendering_id)
        if rendering is not None:
            self.body_view.setPlainText(rendering.body)
            self.body_reasoning_view.setPlainText(rendering.body_reasoning or NO_REASONING_TEXT)

    # -- activate / delete ----------------------------------------------------

    def _on_activate_clicked(self) -> None:
        if self.selected_rendering_id is None:
            return
        with session_scope() as session:
            set_active_rendering(session, self.selected_rendering_id)
        self._refresh(select_rendering_id=self.selected_rendering_id)
        if (
            self._continuity_config is not None
            and self.current_story_id is not None
            and self.current_scene_position is not None
        ):
            story_id = self.current_story_id
            from_position = self.current_scene_position
            self._continuity_busy = True
            self._start_continuity_task(
                lambda: self._regenerate_snapshots_events(story_id, from_position),
                CONTINUITY_REGENERATE_FAILED_TEXT,
            )
            self._refresh(select_rendering_id=self.selected_rendering_id)

    def _on_delete_clicked(self) -> None:
        if self.current_scene_id is None or self.selected_rendering_id is None:
            return
        with session_scope() as session:
            renderings = list_renderings(session, self.current_scene_id)
        target = next((rendering for rendering in renderings if rendering.id == self.selected_rendering_id), None)
        if target is None:
            return
        if len(renderings) == 1:
            self._show_notice(DELETE_SOLE_RENDERING_TEXT)
            return
        if target.is_active:
            self._show_notice(DELETE_ACTIVE_RENDERING_TEXT)
            return
        self._hide_notice()
        if not self._confirm_delete():
            return
        with session_scope() as session:
            delete_rendering(session, target.id)
        self._refresh()

    def _confirm_delete(self) -> bool:
        answer = QMessageBox.question(
            self,
            "Delete Rendering",
            "Delete this rendering version? This cannot be undone.",
        )
        return answer == QMessageBox.StandardButton.Yes

    # -- generate / cancel ----------------------------------------------------

    def _build_messages_or_notify(self) -> list[dict] | None:
        if self.current_scene_id is None or self.current_story_id is None or self._llm_config is None:
            return None
        if self._generating:
            return None
        with session_scope() as session:
            try:
                messages = build_render_messages(session, self.current_story_id, self.current_scene_id)
            except ValueError as error:
                self._show_notice(str(error))
                return None
        self._hide_notice()
        return messages

    def _on_generate_clicked(self) -> None:
        messages = self._build_messages_or_notify()
        if messages is None:
            return
        if self.preview_prompt_checkbox.isChecked():
            dialog = _PromptPreviewDialog(messages, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
        self._start_generation(messages)

    def generate_now(self) -> bool:
        """Start generation for the current scene immediately, bypassing the Preview Prompt
        checkbox -- used by full-story batch rendering (`FullStoryRenderController`), which must
        run unattended across every scene without a modal dialog blocking each one."""
        messages = self._build_messages_or_notify()
        if messages is None:
            return False
        self._start_generation(messages)
        return True

    def _start_generation(self, messages: list[dict]) -> None:
        self._generating = True
        self._generating_scene_id = self.current_scene_id
        self._content_text = ""
        self._reasoning_text = ""
        self._display_text = ""
        self._cancel_requested = False
        self._error_message = None
        self.body_view.clear()
        self.generate_button.hide()
        self.preview_prompt_checkbox.hide()
        self.cancel_button.show()
        self.activate_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.progress_label.setText("Rendering scene prose...")
        self.progress_label.show()

        self._thread = QThread()
        self._worker = _RenderWorker(self._llm_config, messages)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.event_received.connect(self._on_render_event)
        self._worker.error_occurred.connect(self._on_render_error)
        self._worker.finished.connect(self._on_generation_finished)
        self._thread.start()

    def _on_render_event(self, event: RenderEvent) -> None:
        if isinstance(event, RenderContentDelta):
            self._content_text += event.text
            self._display_text += event.text
            self.body_view.setPlainText(self._display_text)
            self._schedule_scroll_body_to_end()
        elif isinstance(event, RenderReasoningDelta):
            self._reasoning_text += event.text
            self._display_text += event.text
            self.body_view.setPlainText(self._display_text)
            self._schedule_scroll_body_to_end()

    def _schedule_scroll_body_to_end(self) -> None:
        # The scrollbar's range is only recomputed during layout, after the text set this
        # event-loop turn has been sized — scrolling immediately after setPlainText() uses the
        # *previous* range and lags one update behind. Scheduling the actual scroll for the
        # next event-loop turn (after that layout pass has run) keeps it accurate. Only ever
        # called while streaming, so it never fights with browsing a previously-saved version.
        QTimer.singleShot(0, self._scroll_body_to_end)

    def _scroll_body_to_end(self) -> None:
        scrollbar = self.body_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_cancel_clicked(self) -> None:
        if not self._generating or self._worker is None:
            return
        answer = QMessageBox.question(self, "Cancel Generation", CANCEL_CONFIRM_TEXT)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._cancel_requested = True
        self._worker.cancel()

    def _on_render_error(self, message: str) -> None:
        self._error_message = message

    def _on_generation_finished(self) -> None:
        # `worker.run()` has already returned by the time `finished` reaches this handler, so
        # the thread's event loop has nothing left to do — `quit()` + `wait()` stop it
        # synchronously and deterministically here, guaranteeing `isRunning()` is False before
        # `self._thread`/`self._worker` can ever be garbage collected. A `deleteLater()` chain
        # instead left teardown timing up to Qt's queued event delivery racing against Python's
        # (possibly cyclic) garbage collector, which could free the QThread while its OS thread
        # was still shutting down and crash the process ("QThread: Destroyed while thread is
        # still running").
        self._thread.quit()
        self._thread.wait()
        scene_id = self._generating_scene_id
        assembled = self._content_text
        body_reasoning = self._reasoning_text or None
        was_cancelled = self._cancel_requested
        error_message = self._error_message
        self.last_generation_cancelled = was_cancelled
        self.last_generation_error = error_message
        self.last_generation_body = assembled
        self.last_continuity_error = None

        self._generating = False
        self._generating_scene_id = None
        self._content_text = ""
        self._reasoning_text = ""
        self._display_text = ""
        self._cancel_requested = False
        self._error_message = None
        self.cancel_button.hide()

        if error_message is not None or was_cancelled:
            self.progress_label.hide()
        else:
            self.progress_label.setText("Rendering scene prose... Done.")

        continuity_started = False
        if assembled:
            with session_scope() as session:
                rendering = create_rendering(session, scene_id=scene_id, body=assembled, body_reasoning=body_reasoning)
                set_active_rendering(session, rendering.id)
                generated_scene = get_scene(session, scene_id)
            if self._continuity_config is not None and generated_scene is not None and not was_cancelled:
                story_id = generated_scene.story_id
                self._continuity_busy = True
                continuity_started = True
                self._start_continuity_task(
                    lambda: self._accept_scene_events(story_id, scene_id),
                    CONTINUITY_UPDATE_FAILED_TEXT,
                )

        if self.current_scene_id is not None:
            self._refresh()
        if scene_id == self.current_scene_id:
            if error_message is not None:
                template = GENERATION_ERROR_SAVED_TEXT if assembled else GENERATION_ERROR_EMPTY_TEXT
                self._show_notice(template.format(error=error_message))
            elif was_cancelled:
                self._show_notice(CANCELLED_SAVED_TEXT if assembled else CANCELLED_EMPTY_TEXT)

        self.generation_finished.emit()
        if not continuity_started:
            self.scene_settled.emit()

    # -- continuity editor ---------------------------------------------------

    def _accept_scene_events(self, story_id: int, scene_id: int) -> Iterator[ContinuityEvent]:
        with session_scope() as session:
            yield from stream_accept_scene(self._continuity_config, session, story_id, scene_id)

    def _regenerate_snapshots_events(self, story_id: int, from_position: int) -> Iterator[ContinuityEvent]:
        with session_scope() as session:
            yield from stream_regenerate_snapshots_from(self._continuity_config, session, story_id, from_position)

    def _start_continuity_task(
        self, events_factory: Callable[[], Iterator[ContinuityEvent]], error_template: str
    ) -> None:
        self._hide_continuity_notice()
        self.progress_label.setText("Creating continuity snapshot...")
        self.progress_label.show()
        thread = QThread()
        worker = _ContinuityWorker(events_factory)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.event_received.connect(self._on_continuity_event)

        def on_error(message: str) -> None:
            self.last_continuity_error = message
            self._show_continuity_notice(error_template.format(error=message))

        worker.error_occurred.connect(on_error)
        worker.finished.connect(self._on_continuity_task_finished)
        self._continuity_thread = thread
        self._continuity_worker = worker
        thread.start()

    def _on_continuity_event(self, event: ContinuityEvent) -> None:
        # Mirrors `_on_render_event`: content and reasoning deltas are both appended into one
        # combined, live-visible stream in the Continuity Snapshot tab (not split into their
        # separate destination tabs until `_refresh()` re-reads the persisted snapshot below),
        # exactly like the Prose tab does today for rendering.
        if isinstance(event, ContinuitySceneStarted):
            self._continuity_display_text = ""
            self._continuity_display_scene_id = event.scene_id
            if event.scene_id == self.current_scene_id:
                self.continuity_snapshot_view.clear()
        elif isinstance(event, ContinuityContentDelta | ContinuityReasoningDelta):
            self._continuity_display_text += event.text
            if self._continuity_display_scene_id == self.current_scene_id:
                self.continuity_snapshot_view.setPlainText(self._continuity_display_text)
                self._schedule_scroll_continuity_to_end()

    def _schedule_scroll_continuity_to_end(self) -> None:
        QTimer.singleShot(0, self._scroll_continuity_to_end)

    def _scroll_continuity_to_end(self) -> None:
        scrollbar = self.continuity_snapshot_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_continuity_task_finished(self) -> None:
        # `worker.run()` has already returned by the time `finished` reaches this handler, so
        # the thread's event loop has nothing left to do — `quit()` + `wait()` stop it
        # synchronously and deterministically here, guaranteeing `isRunning()` is False before
        # `self._continuity_thread`/`self._continuity_worker` can ever be garbage collected. A
        # `deleteLater()` chain instead left teardown timing up to Qt's queued event delivery
        # racing against Python's (possibly cyclic) garbage collector, which could free the
        # QThread while its OS thread was still shutting down and crash the process ("QThread:
        # Destroyed while thread is still running").
        self._continuity_thread.quit()
        self._continuity_thread.wait()
        self._continuity_busy = False
        self._continuity_display_text = ""
        self._continuity_display_scene_id = None
        self.progress_label.setText("Creating continuity snapshot... Done.")
        self._refresh()
        # `_refresh()` just re-set the continuity views' text from the DB (`setPlainText` resets
        # scroll position to the top), which can otherwise race ahead of a scroll-to-end deferred
        # by the last streamed delta -- persisting a snapshot mid-stream (unlike rendering, which
        # persists only after all streaming ends) leaves a real gap where that delta's timer can
        # fire before this handler even runs. Scheduling a fresh scroll here makes the final
        # scrolled-to-end state deterministic regardless of that race.
        self._schedule_scroll_continuity_to_end()
        self.scene_settled.emit()

    # -- notices ---------------------------------------------------------------

    def _show_notice(self, text: str) -> None:
        self.notice_label.setText(text)
        self.notice_label.show()

    def _hide_notice(self) -> None:
        self.notice_label.clear()
        self.notice_label.hide()

    def _show_continuity_notice(self, text: str) -> None:
        self.continuity_notice_label.setText(text)
        self.continuity_notice_label.show()

    def _hide_continuity_notice(self) -> None:
        self.continuity_notice_label.clear()
        self.continuity_notice_label.hide()
