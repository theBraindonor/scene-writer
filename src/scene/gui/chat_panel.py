from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from scene.agent.application.state import ApplicationState
from scene.agent.config import LLMConfig
from scene.agent.coordinator.loop import (
    ContentDelta,
    ReasoningDelta,
    Tool,
    ToolCallFinished,
    ToolCallStarted,
    TurnEvent,
    run_turn,
)
from scene.gui.section_heading import section_heading


class _UserMessageWidget(QWidget):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        body = QLabel(text)
        body.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(section_heading("You"))
        layout.addWidget(body)


class _AutoHeightTextEdit(QTextBrowser):
    """A read-only, markdown-rendering rich-text view that reports its natural content height
    to its layout instead of scrolling internally -- a drop-in replacement for the QLabel it
    used to be, for text that needs setMarkdown() rendering. QTextBrowser rather than plain
    QTextEdit specifically for setOpenExternalLinks(), which only QTextBrowser has."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().documentLayout().documentSizeChanged.connect(self._update_height)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_height()

    def _update_height(self, *_args: object) -> None:
        self.document().setTextWidth(self.viewport().width())
        height = int(self.document().size().height())
        self.setFixedHeight(height + 2 * self.frameWidth())


class _AgentTurnWidget(QWidget):
    """One agent turn's transcript block: reasoning, tool calls, and the streamed answer."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.reasoning_text = ""
        self.answer_text = ""
        self.tool_names: list[str] = []

        self.reasoning_label = _AutoHeightTextEdit()
        self.reasoning_label.setStyleSheet("color: gray;")
        self.reasoning_label.hide()

        self.tool_calls_label = QLabel()
        self.tool_calls_label.setWordWrap(True)
        self.tool_calls_label.hide()

        self.answer_label = _AutoHeightTextEdit()

        layout = QVBoxLayout(self)
        layout.addWidget(section_heading("Assistant"))
        layout.addWidget(self.reasoning_label)
        layout.addWidget(self.tool_calls_label)
        layout.addWidget(self.answer_label)

    def append_reasoning(self, text: str) -> None:
        self.reasoning_text += text
        self.reasoning_label.setMarkdown(self.reasoning_text)
        self.reasoning_label.show()

    def append_answer(self, text: str) -> None:
        self.answer_text += text
        self.answer_label.setMarkdown(self.answer_text)

    def add_tool_call(self, name: str) -> None:
        self.tool_names.append(name)
        self.tool_calls_label.setText("\n".join(f"\U0001f527 {tool_name}" for tool_name in self.tool_names))
        self.tool_calls_label.show()


class _TurnWorker(QObject):
    """Runs one `run_turn` call to completion on a background thread.

    The Qt equivalent of `CoordinatorApp`'s `@work(thread=True)` + `call_from_thread`: each
    yielded `TurnEvent` is forwarded via `event_received`, a queued-connection signal, so the
    main thread applies it to the transcript safely.
    """

    event_received = Signal(object)  # TurnEvent
    finished = Signal()

    def __init__(
        self,
        config: LLMConfig,
        state: ApplicationState,
        tools: list[Tool],
        user_message: str,
        system_prompt: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._state = state
        self._tools = tools
        self._user_message = user_message
        self._system_prompt = system_prompt

    def run(self) -> None:
        for event in run_turn(
            self._config,
            self._state.history,
            self._user_message,
            tools=self._tools,
            system_prompt=self._system_prompt,
        ):
            self.event_received.emit(event)
        self.finished.emit()


class ChatPanel(QWidget):
    """Full-width transcript + input driving the application agent.

    Emits `turn_completed` after every finished turn — `MainWindow` connects to it to sync the
    sidebar's story selection with `ApplicationState.current_story_id` and to refresh the
    entity column, since the agent's tools may have changed either. Also emits
    `tool_call_finished` after *each* tool call within a turn (not just at the end), since a
    single turn can call several tools in sequence (e.g. open_story then select_scene) whose
    combined effect on `ApplicationState` should be visible on screen incrementally, as each
    one lands, rather than staying invisible until the whole turn — including anything slow,
    like a `render_scene` call later in the same turn — finishes.
    """

    turn_completed = Signal()
    tool_call_finished = Signal()
    collapse_toggled = Signal(bool)  # expanded

    EXPANDED_LABEL = "▾ Chat"
    COLLAPSED_LABEL = "▸ Chat"

    def __init__(
        self,
        config: LLMConfig | None,
        state: ApplicationState,
        tools: list[Tool],
        system_prompt: str,
        error: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._state = state
        self._tools = tools
        self._system_prompt = system_prompt
        self._thread: QThread | None = None
        self._worker: _TurnWorker | None = None
        self._active_turn: _AgentTurnWidget | None = None

        self.toggle_button = QPushButton(self.EXPANDED_LABEL)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.toggled.connect(self._on_toggle_expanded)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._on_clear_clicked)

        header_layout = QHBoxLayout()
        header_layout.addWidget(self.toggle_button)
        header_layout.addWidget(self.clear_button)
        header_layout.addStretch()

        self.transcript_layout = QVBoxLayout()
        self.transcript_layout.addStretch()
        self.transcript_container = QWidget()
        self.transcript_container.setLayout(self.transcript_layout)
        # QWidget/QLabel have no background of their own by default, so the transcript would
        # otherwise show through to the window's background, which reads as too close to the
        # surrounding chrome to tell apart. Force a white reading surface with dark text,
        # matching the white background list/text widgets elsewhere in the app get for free.
        self.transcript_container.setStyleSheet("background-color: white; color: black;")

        self.transcript_scroll = QScrollArea()
        self.transcript_scroll.setWidgetResizable(True)
        self.transcript_scroll.setWidget(self.transcript_container)
        # Roughly doubles the transcript's natural (unscrolled) height so more chat history is
        # visible at once without needing to scroll, now that the chat panel lives in the left
        # column at its own preferred height rather than stretching to fill leftover space.
        self.transcript_scroll.setMinimumHeight(140)
        # QScrollArea only recomputes its scrollable range during layout, after the widgets
        # inserted this event-loop turn have been sized — reading maximum() immediately after
        # insertWidget() returns the range from *before* the new content, so the view lags one
        # message behind. rangeChanged fires once that recomputation has actually happened, so
        # scrolling there (rather than right after insertion) keeps the latest message in view.
        self.transcript_scroll.verticalScrollBar().rangeChanged.connect(self._on_transcript_range_changed)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.hide()

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Type a message...")
        self.input_edit.returnPressed.connect(self._on_submit)

        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.transcript_scroll)
        content_layout.addWidget(self.status_label)
        content_layout.addWidget(self.input_edit)

        layout = QVBoxLayout(self)
        layout.addLayout(header_layout)
        layout.addWidget(self.content_widget)

        if error is not None:
            self._show_error(error)

    def _show_error(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.show()
        self.input_edit.setEnabled(False)

    def _on_toggle_expanded(self, expanded: bool) -> None:
        self.content_widget.setVisible(expanded)
        self.clear_button.setVisible(expanded)
        self.toggle_button.setText(self.EXPANDED_LABEL if expanded else self.COLLAPSED_LABEL)
        self.collapse_toggled.emit(expanded)

    def _on_clear_clicked(self) -> None:
        if not self.input_edit.isEnabled():
            # A turn is in flight and still appending to `_state.history` on the worker
            # thread — clearing it now would race that append.
            return
        self._state.history.clear()
        self._clear_transcript()

    def _clear_transcript(self) -> None:
        while self.transcript_layout.count() > 1:
            item = self.transcript_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _on_submit(self) -> None:
        text = self.input_edit.text().strip()
        if not text or self._config is None:
            return
        self.input_edit.clear()
        self._append_transcript_widget(_UserMessageWidget(text))
        self._active_turn = _AgentTurnWidget()
        self._append_transcript_widget(self._active_turn)
        self.input_edit.setEnabled(False)
        self._start_worker(text)

    def _append_transcript_widget(self, widget: QWidget) -> None:
        self.transcript_layout.insertWidget(self.transcript_layout.count() - 1, widget)

    def _on_transcript_range_changed(self, minimum: int, maximum: int) -> None:
        self.transcript_scroll.verticalScrollBar().setValue(maximum)

    def _start_worker(self, user_message: str) -> None:
        self._thread = QThread()
        self._worker = _TurnWorker(self._config, self._state, self._tools, user_message, self._system_prompt)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.event_received.connect(self._on_turn_event)
        self._worker.finished.connect(self._on_worker_finished)
        self._thread.start()

    def _on_turn_event(self, event: TurnEvent) -> None:
        if isinstance(event, ToolCallFinished):
            self.tool_call_finished.emit()
            return
        block = self._active_turn
        if block is None:
            return
        if isinstance(event, ReasoningDelta):
            block.append_reasoning(event.text)
        elif isinstance(event, ContentDelta):
            block.append_answer(event.text)
        elif isinstance(event, ToolCallStarted):
            block.add_tool_call(event.name)

    def _on_worker_finished(self) -> None:
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
        self.input_edit.setEnabled(True)
        self.input_edit.setFocus()
        self._active_turn = None
        self.turn_completed.emit()
