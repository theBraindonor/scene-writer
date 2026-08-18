---
archived: false
campaign: c003-coordinating-agent
created_by: John Hoff
created_on: '2026-08-18T18:30:13Z'
depends_on:
- e005-coordinator-cli-state-display
kind: scripted
name: e005a-coordinator-tui-streaming
regions:
- agent
- cli
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T19:40:39Z'
---

# E005a — Coordinator TUI Streaming, Message Blocks, and Multi-line Input

## Requirements
- Add `stream_complete(config, messages, tools=None)` to `scene.agent.llm`, mirroring `complete()`'s kwargs construction (same `api_base`/`api_key` handling) but passing `stream=True` to `litellm.completion()` and returning the raw streaming iterator. Keep the existing non-streaming `complete()` as-is; nothing requires removing it.
- Replace `scene.agent.coordinator.loop.run_turn`'s implementation with a generator that streams the model's response instead of blocking for a single complete reply. As it consumes `stream_complete()`'s chunks, it yields structured events in the order they occur: reasoning-text deltas (only for models/providers that emit them), answer-text deltas, a tool-call-started notice (tool name only, emitted once per call as soon as that call's name is known — not its arguments), and a final turn-complete event once the model's plain-text reply is done and no further tool calls remain. Streamed tool-call fragments (which arrive incrementally, keyed by index) must be accumulated into complete tool calls before being dispatched. The generator must still perform the existing multi-round tool-calling loop exactly as before — dispatch each tool call via the registry, feed its result back as a tool-role message, and continue streaming — and must still mutate the passed-in `history` list the same way (system/user/assistant-with-tool_calls/tool/assistant), so `CoordinatorState` and the story tools continue to work completely unmodified.
- Update `CoordinatorApp`'s transcript: replace the flat `RichLog` with a scrollable column of distinct message blocks — one block per user message, one block per agent turn. Each agent-turn block shows, in order: a "Thinking" section (only present when reasoning content is actually received for that turn), a list of tool-call notices (tool name only, no arguments or results) for every tool call made during that turn, and the streamed answer text — all updated live as events arrive. The Thinking section is expanded automatically while reasoning text is actively streaming in, then automatically collapses once reasoning ends (the turn moves on to answer text, a tool call, or completion); a small click-to-toggle control on the section persists afterward so the developer can manually re-expand or re-collapse it at any time. Show a lightweight processing indicator while a turn is in progress (before any answer text has streamed, and while further tool calls are still being made), clearing it once the turn completes.
- Render both the Thinking section's reasoning text and the streamed answer text as Markdown (e.g. via Textual's `Markdown` widget) rather than as plain text, so formatting the model produces — lists, emphasis, code blocks, etc. — displays correctly. Re-render as new content streams in rather than only once at the end.
- Replace the single-line `Input` with a multi-line text box, 3 lines tall, that scrolls when its content exceeds that height. Enter submits the current message (routed through the same `/quit`/`/clear`/chat handling as today); Shift+Enter inserts a newline. Terminal support for distinguishing Shift+Enter from plain Enter is inconsistent — if it proves unreliable during implementation, document and use whatever fallback binding (e.g. Ctrl+Enter) actually works reliably, rather than silently losing the ability to enter a newline.
- Cover the new streaming `run_turn` with unit tests: a plain streamed reply (content deltas followed by a turn-complete event); reasoning deltas interleaved with answer deltas; a single tool-call round trip (the tool-call-started event fires exactly once, by name only); multiple tool calls streamed within one turn; and confirmation that the `history` left behind after fully consuming the generator matches the same message shapes the previous blocking implementation produced. Cover the TUI's message-block rendering (user vs. agent blocks), the Thinking section's expand-while-streaming/auto-collapse-when-done/manual-toggle behavior, Markdown rendering of reasoning and answer text, tool-call notices (name only), the processing indicator, and the multi-line input's submit-vs-newline behavior with Textual's headless `App.run_test()`, mocking the streaming completion call so no real network call is made.

## Rationale
Requested by the developer as a follow-on set of TUI improvements once the two-pane
Textual interface (`e005-coordinator-cli-state-display`) was in place. Streaming reduces
perceived latency and lets the developer watch the agent work in real time rather than
staring at a blank pane until a full reply arrives; this matters more now that turns can
involve multiple tool-calling round trips, each of which previously appeared to hang the
UI until the entire chain finished. Organizing messages into distinct You/Coordinator
blocks (rather than a flat scrolling log) and adding a processing indicator make an
increasingly capable, longer-running conversation legible. Showing tool-call names but
never their arguments or results keeps a block from becoming noisy scaffolding. Thinking
mirrors the pattern of visibly reasoning while the model is actually reasoning, then
getting out of the way automatically once it's done, while remaining available on demand
via its toggle rather than being lost. Rendering Markdown rather than plain text matters
because models routinely format lists, emphasis, and code blocks in their replies, which
would otherwise show up as literal asterisks and backticks. A 3-line scrolling input
replaces a single-line box that couldn't comfortably hold a longer instruction.

This encounter's Plan changes the shipped code of `e001-agent-llm-runtime` (`scene/agent/llm.py`),
`e002-coordinator-tool-loop` (`scene/agent/coordinator/loop.py`), and `e005-coordinator-cli-state-display`
(`scene/cli/coordinator_app.py`) — all completed and locked encounters. Per this campaign's
established precedent (e003 recording a necessitated fix to e001's locked code, e005 recording
a necessitated change to e004's locked code), those changes are recorded here rather than by
reopening the encounters that shipped the code being changed.

## Plan
1. Add `stream_complete(config, messages, tools=None)` to `scene/agent/llm.py`, reusing `complete()`'s kwargs-construction logic but with `stream=True`, returning the raw litellm stream iterator.
2. Rewrite `scene/agent/coordinator/loop.py`'s `run_turn` into a generator yielding small event dataclasses (e.g. `ReasoningDelta`, `ContentDelta`, `ToolCallStarted`, `TurnComplete`), consuming `stream_complete()`'s chunks, accumulating streamed tool-call fragments by index into complete tool calls once the stream for that round ends, then performing the same history mutation and tool dispatch as the current implementation before looping to the next streamed call when more tool calls remain.
3. Update `scene/cli/coordinator_app.py`: replace the `RichLog` transcript with a `VerticalScroll` of message-block widgets (one per user message, one per agent turn), rendering reasoning/answer text via Textual's `Markdown` widget re-updated as content streams in; add a `TextArea`-based multi-line input (3 lines tall, scrolling, Enter-submits/Shift+Enter-newline key handling, with a documented fallback binding if Shift+Enter proves unreliable); update `_respond`'s worker to iterate the new streaming `run_turn` generator, using `call_from_thread` to push each event into the current agent-turn block's widgets as it arrives — expanding the Thinking section on the first `ReasoningDelta` and auto-collapsing it on the first `ContentDelta`/`ToolCallStarted`/`TurnComplete` that follows reasoning, while leaving its toggle control able to override that state afterward — plus tool-call notices, answer text, and the processing indicator cleared on `TurnComplete`.
4. Update/add unit tests for the streaming `run_turn` under `test/scene/agent/coordinator/test_loop.py`, covering the scenarios in Requirements.
5. Update `test/scene/cli/test_coordinator_app.py` for the new message-block structure, Thinking expand/collapse/toggle behavior, Markdown rendering, tool-call notices, processing indicator, and multi-line input submit behavior, mocking the streaming completion call.
6. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-coordinator chat` against a running LM Studio server (using a reasoning-capable model if one is configured, to also exercise the Thinking section) and confirm: replies stream in visibly rather than appearing all at once; user and agent messages render as distinct blocks; Markdown (lists, emphasis, code blocks) in a reply renders formatted rather than as literal syntax; a processing indicator shows while waiting/streaming and clears on completion; asking it to create or update a story shows a tool-call notice by name only, with no arguments or results visible; a Thinking section (when the model provides one) expands live while reasoning streams and auto-collapses once it's done, with its toggle still able to re-expand it afterward; the input box is 3 lines tall and scrolls with longer text; Enter sends and Shift+Enter (or the documented fallback) inserts a newline.

## Log

### Review - 2026-08-18T18:37:20Z - John Hoff

Reviewed e005a-coordinator-tui-streaming against the two applicable world-assigned lore items (linting, unit-testing; no additional region-specific lore on agent/cli) and against the real shipped code of e001/e002/e005. The Rationale's justification for touching those three locked encounters' code correctly follows this campaign's established precedent (e003->e001, e005->e004), citing exact files and matching the prior pattern's wording. Confirmed via grep that run_turn and scene.agent.llm.complete have no consumers beyond coordinator_app.py and loop.py respectively, so the Plan's touched-file list is complete. Streamed tool-call fragment accumulation keyed by index is a technically sound, standard pattern against stream_complete()'s raw iterator, and testing a sync generator-based run_turn plus a Textual app with live-updating widgets is realistically achievable with the project's existing tooling (plain pytest, pytest-asyncio, headless App.run_test()) with no new test infrastructure required. One real but minor gap: the Requirements require the ToolCallStarted event to fire as soon as a tool call's name is known mid-stream, while the Plan's description of tool-call handling emphasizes only end-of-round fragment accumulation before dispatch, leaving the earlier incremental name-detection step implicit rather than stated - worth tightening during implementation but not a lore conflict. stream_complete() also isn't named as its own test target alongside the Plan's two listed test files, though the unit-testing lore's mirroring rule and blanket pytest-green requirement should catch this in practice. No lore conflicts found; PASS-WITH-NOTES.

### Completed - 2026-08-18T19:40:39Z - John Hoff

Verified: pdm run pytest passes 189/189 with 100% coverage, pdm run lint zero errors. Delivered: stream_complete() in scene/agent/llm.py; scene/agent/coordinator/loop.py's run_turn rewritten into a generator yielding ReasoningDelta/ContentDelta/ToolCallStarted/TurnComplete events (tool-call fragments accumulated by index, ToolCallStarted fires as soon as a call's name is known); scene/cli/coordinator_app.py rewritten with message-block widgets (UserMessage and AgentTurnBlock, both Markdown-rendered, styled consistently), a Thinking section that expands while reasoning streams and auto-collapses when done (manual toggle always available), tool-call-name-only notices, a processing indicator, and a ChatInput (TextArea subclass) with Enter-to-send and Ctrl+J/Shift+Enter for a newline.

Manually verified against the live LM Studio server end-to-end (outside the TUI rendering layer, which this sandboxed shell cannot drive interactively): real streaming reasoning -> tool call -> answer events parsed correctly; a numbered Markdown list generated and a tool call persisted style guidance, confirmed via scene-data.

Follow-up fixes made during this encounter based on the developer's feedback after the initial implementation, each with regression test coverage:
1. User messages restyled to match agent-turn blocks (shared .message-block CSS, distinguished by border color).
2. Fixed message blocks blowing out/truncating: Vertical's default height:1fr was inherited by AgentTurnBlock/UserMessage, forcing each into an equal fractional share of the transcript instead of sizing to content; changed to height:auto so blocks size naturally and the transcript actually scrolls once content overflows.
3. Fixed the chat input appearing single-line despite height:3 - its border was consuming 2 of those 3 rows; bumped to height:4 for 2 visible content rows per the developer's ask.
4. Fixed ordered/unordered Markdown lists blowing out block height: traced to a Textual library quirk where Markdown's list-item wrapper is a raw Horizontal with no height override, inheriting the same height:1fr default from finding #2; fixed with a targeted CSS override on MarkdownOrderedList/MarkdownBulletList's Horizontal children.
5. Added continuous auto-scroll: the transcript now scrolls to bottom after every individual streamed event, not just once at turn start/end.

No deviations from the reviewed Plan beyond these developer-directed follow-ups, which were all implementation-detail-level (widget structure, CSS) rather than scope changes.
