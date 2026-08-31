---
archived: false
campaign: c010-application-agent
created_by: John Hoff
created_on: '2026-08-31T04:34:19Z'
depends_on: []
kind: scripted
name: e020-chat-panel-markdown-and-focus
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-31T05:02:20Z'
---

## Requirements

Two small UX fixes to `src/scene/gui/chat_panel.py`'s chat surface for the application agent,
both raised directly by the developer after using it live:

- The Assistant's reasoning and answer text in `_AgentTurnWidget` render as formatted rich
  text from the markdown the agent actually produces — headings, emphasis, lists, code
  blocks/spans, and clickable links — instead of showing the raw literal markdown syntax
  (`**bold**`, `- item`, etc.) as plain text. Rendering updates live as each delta streams
  in, same as today. The person's own typed message (`_UserMessageWidget`) and the tool-call
  names list (`tool_calls_label`) are unaffected — see Rationale for why.
- After a turn finishes (`ChatPanel._on_worker_finished`), keyboard focus returns to
  `input_edit` automatically, so the person can start typing their next message immediately
  without first clicking back into the field. Today `input_edit.setEnabled(True)` re-enables
  it but never restores focus.

## Rationale

**`QTextEdit.setMarkdown()`, not a third-party markdown-to-HTML dependency.** Qt has shipped
a built-in markdown parser on `QTextDocument`/`QTextEdit` since Qt 5.14 (`setMarkdown()` /
`toMarkdown()`); confirmed present and working in this project's actual PySide6 (6.11.2) via
a throwaway spike: feeding `"**bold**, *italic*, a [link](...), - item one, \`\`\`code
block\`\`\`"` through `setMarkdown()` and reading back `toPlainText()` returns the rendered
text with the markdown syntax characters stripped (`"bold"`, `"italic"`, list items, code
block contents) — proof it's genuinely parsing and formatting, not passing text through
unchanged. This avoids adding a new PyPI dependency (e.g. the `markdown` package) for
something the GUI toolkit already does natively.

**`QLabel` → an auto-sizing `QTextEdit`, not a plain rich-text `QLabel`.** `QLabel` only
understands a fixed HTML subset via `setText()` with rich-text auto-detection — it has no
markdown parser at all, so `setMarkdown()` isn't an option on it. Swapping to `QTextEdit` (the
widget that actually owns `setMarkdown()`) means also solving the layout problem `QLabel`
solved for free: a bare `QTextEdit` is a scrolling box with its own scrollbars and a size
policy independent of its content, wrong for a transcript entry that needs to report its
natural content height to `transcript_layout`/`transcript_scroll`, exactly like
`QLabel.setWordWrap(True)` already does and like `list_sizing.py`'s
`fit_list_height_to_contents` already solves for `QListWidget`. Confirmed via the same spike
that `document().setTextWidth(viewport_width)` followed by reading `document().size().height()`
returns a real, usable height (130.0 for the spike's sample markdown) once the document knows
its available width.

**A small private `_AutoHeightTextEdit` subclass in `chat_panel.py`, not a new shared
`text_sizing.py` module.** Nothing else in the GUI needs a markdown-rendering auto-height text
widget yet — `list_sizing.py` exists as its own module because `fit_list_height_to_contents`
already has multiple `QListWidget` call sites across `entity_column/`; this doesn't, so
extracting a shared module now would be speculative. If a second consumer shows up later,
it can be promoted then.

**Only the Assistant's reasoning/answer text renders markdown — not the person's own message
or the tool-call list.** Reinterpreting the person's own typed words as markdown could
surprise them (a line they typed starting with `"- "` silently becoming a bullet they didn't
intend), and `tool_calls_label` only ever holds short wrench-emoji-prefixed tool names with no
formatting need. Only text the *agent* generates — which already writes in prose meant to be
read formatted — gets the rich-text treatment.

**Re-render the whole accumulated buffer on every delta, not incremental patching.**
`append_reasoning`/`append_answer` already accumulate the full text in `self.reasoning_text`/
`self.answer_text` and re-set the widget's content from that accumulated string on every
delta — this doesn't change. A rendered link is also made clickable
(`setOpenExternalLinks(True)`) since a real hyperlink that can't be opened reads as broken,
not as a deliberate limitation.

**Focus fix is a one-line addition, not a new mechanism.** `_on_worker_finished` already runs
on the main thread and already re-enables `input_edit` — `QLineEdit.setFocus()` right after
`setEnabled(True)` is sufficient; Qt has no "restore previous focus automatically on
re-enable" behavior of its own, so this has to be explicit.

## Plan

1. `src/scene/gui/chat_panel.py`:
   - Add imports: `Qt` from `PySide6.QtCore` (for `Qt.ScrollBarPolicy.ScrollBarAlwaysOff`);
     `QFrame`, `QSizePolicy`, `QTextEdit` from `PySide6.QtWidgets` (`QLabel` stays imported —
     still used by `_UserMessageWidget`, `status_label`, `tool_calls_label`).
   - New private class, defined above `_AgentTurnWidget`:
     ```python
     class _AutoHeightTextEdit(QTextEdit):
         """A read-only, markdown-rendering QTextEdit that reports its natural content
         height to its layout instead of scrolling internally -- a drop-in replacement for
         the QLabel it used to be, for text that needs setMarkdown() rendering."""

         def __init__(self, parent: QWidget | None = None) -> None:
             super().__init__(parent)
             self.setReadOnly(True)
             self.setOpenExternalLinks(True)
             self.setFrameStyle(QFrame.Shape.NoFrame)
             self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
             self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
             self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
             self.document().documentLayout().documentSizeChanged.connect(self._update_height)

         def resizeEvent(self, event) -> None:
             super().resizeEvent(event)
             self._update_height()

         def _update_height(self, *_args: object) -> None:
             self.document().setTextWidth(self.viewport().width())
             height = int(self.document().size().height())
             self.setFixedHeight(height + 2 * self.frameWidth())
     ```
     Both `documentSizeChanged` (content changes) and `resizeEvent` (width changes) trigger
     `_update_height` — deliberately redundant/cheap rather than relying on exact Qt signal
     ordering being sufficient on its own; verify during Verification that resizing the window
     doesn't leave stale/clipped heights.
   - `_AgentTurnWidget.__init__`: change `self.reasoning_label = QLabel()` and
     `self.answer_label = QLabel()` to `_AutoHeightTextEdit()`; drop the now-inapplicable
     `.setWordWrap(True)` calls (QTextEdit wraps by default); keep
     `reasoning_label.setStyleSheet("color: gray;")` and `.hide()` (both still valid on
     `QTextEdit`) — confirm during the manual smoke check that the gray styling still reads
     correctly against rendered rich text, adjusting if needed.
   - `append_reasoning`/`append_answer`: change `self.reasoning_label.setText(self.reasoning_text)`
     / `self.answer_label.setText(self.answer_text)` to `.setMarkdown(...)`.
   - `_on_worker_finished`: immediately after `self.input_edit.setEnabled(True)`, add
     `self.input_edit.setFocus()`.

2. Tests, `test/scene/gui/test_chat_panel.py`:
   - Update the two existing reads of the old `QLabel` API to the `QTextEdit` equivalent:
     `agent_blocks[0].answer_label.text()` → `.toPlainText()` in
     `test_sending_message_streams_scripted_response`, and
     `block.reasoning_label.text()` → `.toPlainText()` in
     `test_reasoning_and_tool_calls_are_shown` (both existing sample strings — `"Hello
     there!"`, `"Thinking..."` — contain no markdown syntax, so the plain-text reads are
     unaffected by the switch and stay exact matches).
   - New `test_answer_renders_markdown_formatting`: script a reply containing
     `"**bold** and a [link](https://example.com)"`, send it, and assert
     `block.answer_label.toPlainText() == "bold and a link"` (markdown syntax stripped, proof
     it rendered rather than displaying literally) and
     `block.answer_label.toHtml()` contains `href="https://example.com"` (the link survived
     as a real hyperlink, confirming `setOpenExternalLinks`/link rendering took effect).
   - New `test_input_regains_focus_after_turn_completes`: after `send(qtbot, panel, ...)`
     returns (turn already completed), assert `panel.input_edit.hasFocus()` is `True`. If
     `hasFocus()` proves unreliable under the test environment's offscreen/headless window
     activation (a known source of flakiness for Qt focus assertions in CI), fall back to
     asserting `QApplication.focusWidget() is panel.input_edit` instead, calling
     `panel.activateWindow()` before sending if needed — confirm which is reliable while
     implementing rather than guessing here.

3. Manual smoke check via the `run` skill: send a message that provokes a markdown-rich
   reply (e.g. ask for a short bulleted list with a bolded term and a link) and confirm it
   renders as real formatting (not literal asterisks/dashes), the link is clickable, and the
   transcript entry's height fits its content with no clipping or leftover blank space at any
   window width (resize the window to check); then send a plain message and confirm the
   cursor is already blinking in the input field immediately after the reply finishes,
   without clicking it first.

## Verification

- `pdm run pytest` — full suite passes, including the two updated and two new
  `test/scene/gui/test_chat_panel.py` cases, with the auto-generated `htmlcov/index.html`
  coverage report covering the changed code.
- `pdm run lint` — clean (ruff, 120-char line length).
- Manual smoke check as described in Plan step 3, via the `run` skill.

## Log

### Review - 2026-08-31T04:35:20Z - John Hoff

This scripted encounter's Plan and Verification satisfy both applicable lore items: it explicitly gates completion on `pdm run lint` (ruff, 120-char) and `pdm run pytest` (full suite passing with the auto-generated HTML coverage report), and its test changes correctly extend `test/scene/gui/test_chat_panel.py` to mirror the modified `src/scene/gui/chat_panel.py`, covering both new behaviors (markdown rendering, focus restoration) as well as updating the two existing assertions affected by the `QLabel` → `QTextEdit` swap; no conflicts or gaps against the `linting` or `unit-testing` lore were found, and no concerns need flagging as unverified.

### Message - 2026-08-31T04:56:31Z - John Hoff

Deviation found during implementation: the Plan's `_AutoHeightTextEdit` sketch subclassed `QTextEdit` and called `setOpenExternalLinks(True)` on it, but that method belongs to `QTextBrowser` (a `QTextEdit` subclass), not plain `QTextEdit` itself — this raised `AttributeError` on the very first construction, caught immediately by the existing test suite. Fixed by subclassing `QTextBrowser` instead; it inherits `setMarkdown()`/`toMarkdown()` from `QTextEdit` unchanged, so nothing else in the Plan needed to change. Confirmed via `QTextBrowser` has both `setMarkdown` and `setOpenExternalLinks` before making the swap.

Verification passed: `pdm run pytest` (732 tests), `pdm run lint` clean. Live manual smoke test via an ad hoc driver script against a real MainWindow and a real configured OpenRouter model: the agent's reply rendered as genuine rich text (`toHtml()` showed real `<span style="font-weight:700;">`/`<ul>` markup for bold/list content), `toPlainText()` contained no literal markdown syntax characters (`**`, `- `, `](`), `input_edit.hasFocus()` was `True` and `QApplication.focusWidget()` was the input field immediately after the turn completed with no click needed, and the transcript entry's auto-computed height responded correctly to window-width changes (96px → 82px when widened, more text fit horizontally) with no clipping.

### Completed - 2026-08-31T05:02:20Z - John Hoff

Verification passed: pdm run pytest (732 tests), pdm run lint clean, live manual smoke test against a real MainWindow and a real configured OpenRouter model confirmed both fixes. Delivered as planned with one implementation deviation (QTextEdit -> QTextBrowser for setOpenExternalLinks, logged in this encounter's Log) — the Assistant's reasoning/answer text now renders real markdown formatting via Qt's native setMarkdown(), and the chat input regains keyboard focus automatically once a turn completes.
