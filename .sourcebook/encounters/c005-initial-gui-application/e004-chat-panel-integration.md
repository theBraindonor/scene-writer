---
archived: false
campaign: c005-initial-gui-application
created_by: John Hoff
created_on: '2026-08-20T22:47:25Z'
depends_on:
- e001-gui-app-skeleton-and-sidebar
- e002-entity-column-crud
- e003-rendering-column
kind: scripted
name: e004-chat-panel-integration
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-21T04:05:44Z'
---

# E004 — Chat Panel Integration

## Requirements
- Replace the chat-panel placeholder from `e001` with a full-width transcript + input widget:
  a scrollable transcript area showing user messages and agent turns (reasoning, tool calls, and
  the final answer, streamed live), and a text input that submits on Enter — functionally
  equivalent to `CoordinatorApp`'s transcript/input behavior, adapted to Qt widgets.
- On submit, run `scene.agent.coordinator.loop.run_turn` against a `CoordinatorState` owned by
  `MainWindow`, using the existing tool builders (`build_story_tools`/`build_scene_tools`/
  `build_character_tools`/`build_location_tools`) built once against that state — on a
  background thread, delivering each yielded `TurnEvent` (`ReasoningDelta`/`ContentDelta`/
  `ToolCallStarted`/`TurnComplete`) to the main thread via Qt signals (queued connection), per
  the campaign's Qt-signals-not-asyncio design decision.
- Load the coordinating agent's `LLMConfig` via `scene.agent.config.get_llm_config
  (AgentRole.COORDINATING)` at startup; if it fails, show an error (e.g. a status message in the
  chat panel) and disable sending, matching `scene-coordinator chat`'s existing error handling
  in `scene/cli/coordinator.py` rather than crashing the app.
- Wire the two-way story sync the campaign calls for: selecting a story in the sidebar
  (`current_story_changed` from `e001`) sets `CoordinatorState.current_story_id` directly, no
  tool call involved. After every completed turn, re-read `state.current_story_id`; if it
  differs from the sidebar's current selection (the agent created, selected, or archived a
  story via its tools), update the sidebar's selection through the same path a user's own
  selection would take, so `e002`'s entity column and `e003`'s rendering column follow it.
- Regardless of whether the story id changed, refresh `e002`'s entity column after every
  completed turn (the agent's tools may have edited scenes/characters/locations within the same
  story), mirroring how `CoordinatorApp._refresh_story_pane` already runs unconditionally after
  every turn today.
- Cover with tests in `test/scene/gui/test_chat_panel.py` (or `test_main_window.py`), using the
  same `monkeypatch`-`stream_complete` scripting pattern as `test/scene/cli/
  test_coordinator_app.py`, driven via `pytest-qt`'s `qtbot`: sending a message streams the
  scripted response into the transcript; a scripted tool call that creates a new story updates
  `current_story_id` and the sidebar/entity column follow it after the turn completes; a
  scripted tool call that edits an existing scene/character/location is reflected in the entity
  column after the turn completes.

## Rationale
Completes the campaign's four-region layout by wiring the last placeholder to the same
coordinating agent `scene-coordinator chat` already drives, per the campaign's "reuse the agent
as-is" design decision — no new tool, prompt, or agent-state surface. This is also where the
campaign's two-way story-sync design decision is actually exercised end-to-end for the first
time: `e001` emits `current_story_changed` and `e002`/`e003` consume it, but nothing before this
encounter ever changes `current_story_id` from a source other than the sidebar itself. Depends
on `e001` (window shell, sidebar, `current_story_changed`), `e002` (entity column to refresh),
and `e003` (rendering column, refreshed transitively through `e002`'s scene selection) because a
completed turn must be able to refresh all three.

## Plan
1. Create `src/scene/gui/chat_panel.py` with the transcript and input widgets, plus a small
   `QObject`-based worker (running on a `QThread`) exposing a slot that calls `run_turn` and
   signals matching each `TurnEvent` variant — the Qt equivalent of `CoordinatorApp`'s
   `@work(thread=True)` + `call_from_thread` pattern.
2. Wire `MainWindow` (from `e001`) to own the shared `CoordinatorState` and tool list, replace
   the chat placeholder with `ChatPanel`, and load `LLMConfig` via `get_llm_config
   (AgentRole.COORDINATING)` at construction time, handling the failure case per Requirements.
3. Connect the sidebar's `current_story_changed` (from `e001`) to set
   `CoordinatorState.current_story_id`; connect the chat worker's turn-complete signal to
   re-check `state.current_story_id` against the sidebar and, if different, drive the sidebar's
   selection to match; unconditionally refresh `e002`'s entity column after every completed
   turn.
4. Add `test/scene/gui/test_chat_panel.py` covering the scenarios in Requirements, scripting
   `stream_complete` the same way `test/scene/cli/test_coordinator_app.py` already does.
5. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-writer`: chat with the coordinating agent to create a new story
  and confirm the sidebar, entity column, and rendering column all follow it; chat to edit a
  scene/character/location in the currently selected story and confirm the entity column
  reflects the change once the turn completes.

## Log

### Review - 2026-08-21T02:50:04Z - John Hoff

Reviewed against the two applicable world lore items (linting, unit-testing) — both are explicitly and concretely satisfied: the Plan runs `pdm run lint` with zero-errors required in Verification, and adds `test/scene/gui/test_chat_panel.py` (or `test_main_window.py`), correctly mirroring the `gui` region's `src/scene/gui` path, with concrete scenarios (streamed transcript, story-id sync on agent-driven story changes, entity-column refresh after edits) scripted in the same `stream_complete`/`qtbot` pattern as the existing `test_coordinator_app.py`, gated on `pdm run pytest` passing. No conflicts found; encounter is reviewable and lore-consistent.

### Message - 2026-08-21T04:05:40Z - John Hoff

Automated verification: `pdm run pytest` (357 passed) and `pdm run lint` (zero errors) both pass. Developer performed manual verification directly and reported three UX issues, all fixed and covered by new tests: (1) the transcript wasn't scrolling to the newest message — `verticalScrollBar().maximum()` was read immediately after inserting a widget, before Qt recomputed the scrollable range, so the view lagged one message behind; fixed by scrolling in response to the scrollbar's `rangeChanged` signal instead. (2) the transcript background read too close to the surrounding window chrome — gave `transcript_container` an explicit white background with black text. (3) added the requested UX: the "Chat" heading is now a `▾ Chat`/`▸ Chat` toggle button that collapses/expands the transcript and input, with a Clear button next to it (visible only while expanded) that empties both the transcript and `CoordinatorState.history`, guarded against clearing while a turn is in flight on the background thread.

### Completed - 2026-08-21T04:05:44Z - John Hoff

All tests pass (357/357) and lint is clean. Developer performed manual verification directly and reported three UX issues (scroll lag, low-contrast transcript background, missing collapse/clear controls), all fixed and covered by new tests per the message above. Chat panel now drives the coordinating agent on a background QThread with full two-way story sync exercised end-to-end for the first time in this campaign.
