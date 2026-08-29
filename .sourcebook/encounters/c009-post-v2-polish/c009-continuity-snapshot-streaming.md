---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-29T22:30:52Z'
depends_on: []
kind: scripted
name: c009-continuity-snapshot-streaming
regions:
- agent
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-29T23:36:25Z'
---

# Continuity snapshot streaming

## Requirements

- The "Continuity Snapshot" and "Continuity Snapshot Reasoning" tabs in the
  GUI's rendering column (`RenderingColumn` in `src/scene/gui/rendering_column.py`)
  must show the continuity editor's output streaming in live, chunk by chunk,
  as the LLM generates it — the same live-update experience the "Prose" tab
  already has for scene rendering.
- This applies to both existing triggers of a continuity task: accepting a
  freshly-rendered scene (`_on_generation_finished`) and regenerating the
  snapshot chain after activating a different rendering version
  (`_on_activate_clicked`).
- During a multi-scene regeneration chain, only stream into the visible tabs
  while the scene currently being processed is the one selected in the
  entity column; scenes elsewhere in the chain must not flash unrelated text
  into the tabs the user is looking at.
- No change to the CLI's Textual TUI (`src/scene/cli/render_app.py`), which
  is out of scope for this encounter and keeps calling the existing
  non-streaming `accept_scene`/`regenerate_snapshots_from`.

## Rationale

Scene rendering (the "Prose" tab) already streams live via `stream_render`
(`src/scene/agent/rendering.py`) and the `_RenderWorker`/`event_received`
Qt signal plumbing in `rendering_column.py`. Continuity snapshot generation
uses the same underlying LiteLLM client (`scene.agent.llm`, which already
exposes both `complete` and `stream_complete` off one shared `_build_kwargs`)
but currently calls the blocking `run_continuity_edit`/`complete`, so the
"Continuity Snapshot" tab only ever gets a single, one-shot `setPlainText`
once the whole snapshot is done (`_refresh_continuity_snapshot`). Users
watching a continuity update get no feedback beyond the "Creating continuity
snapshot..." progress label added in e004, unlike the prose tab which visibly
fills in as it's written. Bringing continuity to parity closes that gap using
architecture that's already proven for rendering.

## Plan

1. **`src/scene/agent/continuity.py`** — add streaming support alongside the
   existing non-streaming functions (which stay untouched, since
   `src/scene/cli/render_app.py` still calls them directly):
   - Import `stream_complete` from `scene.agent.llm` (alongside the existing
     `complete` import) and `Iterator` from `collections.abc`.
   - Add `ContinuityReasoningDelta(text: str)`, `ContinuityContentDelta(text: str)`,
     and `ContinuityComplete(text: str, reasoning: str = "")` frozen
     dataclasses, plus `ContinuitySceneStarted(scene_id: int)` and
     `ContinuitySceneComplete(scene_id: int, snapshot: ContinuitySnapshot)`.
     Union them as `ContinuityEvent`.
   - Add `stream_continuity_edit(config, messages) -> Iterator[ContinuityEvent]`,
     a line-for-line mirror of `stream_render` in `rendering.py`: iterate
     `stream_complete(config, messages)`, yield `ContinuityReasoningDelta`/
     `ContinuityContentDelta` per chunk, then yield one final
     `ContinuityComplete` with the assembled text and reasoning.
   - Add `stream_accept_scene(config, session, story_id, scene_id) -> Iterator[ContinuityEvent]`:
     build messages via the existing `build_continuity_messages`, yield
     `ContinuitySceneStarted(scene_id)`, re-yield every delta from
     `stream_continuity_edit`, and on its `ContinuityComplete`, persist via
     `delete_snapshot` + `create_snapshot` (exactly as `accept_scene` does
     today) and yield `ContinuitySceneComplete(scene_id, snapshot)` in place
     of the raw `ContinuityComplete`.
   - Add `stream_regenerate_snapshots_from(config, session, story_id, from_position) -> Iterator[ContinuityEvent]`:
     same structure as `regenerate_snapshots_from` (invalidate from position,
     iterate scenes in order, break at the first scene with no active
     rendering), but `yield from stream_accept_scene(...)` per scene instead
     of calling `accept_scene`.

2. **`src/scene/gui/rendering_column.py`**:
   - Swap the `accept_scene, regenerate_snapshots_from` import for
     `stream_accept_scene, stream_regenerate_snapshots_from`, and import the
     new `ContinuityContentDelta`, `ContinuityReasoningDelta`,
     `ContinuitySceneStarted`, `ContinuityEvent` names. Add `Iterator` to the
     existing `collections.abc` import.
   - `_ContinuityWorker`: add `event_received = Signal(object)`; change its
     constructor to take `events_factory: Callable[[], Iterator[ContinuityEvent]]`
     instead of `target: Callable[[], None]`; `run()` iterates
     `for event in self._events_factory(): self.event_received.emit(event)`
     inside the existing try/except, still always emitting `finished` (same
     never-swallow-a-dead-thread guarantee as `_RenderWorker.run`).
   - Replace `_accept_scene_task`/`_regenerate_snapshots_task` with generator
     methods `_accept_scene_events(story_id, scene_id)` /
     `_regenerate_snapshots_events(story_id, from_position)`, each opening
     `with session_scope() as session: yield from stream_accept_scene(...)` /
     `yield from stream_regenerate_snapshots_from(...)` — the session stays
     open for the generator's full lifetime, on the worker thread.
   - `_start_continuity_task`: rename its `target` parameter to
     `events_factory`, construct `_ContinuityWorker(events_factory)`, and
     connect `worker.event_received.connect(self._on_continuity_event)`.
     Update both call sites (`_on_generation_finished`,
     `_on_activate_clicked`) to pass the new generator methods.
   - Add instance state in `__init__`: `self._continuity_content_text = ""`,
     `self._continuity_reasoning_text = ""`,
     `self._continuity_display_scene_id: int | None = None`.
   - Add `_on_continuity_event(self, event: ContinuityEvent) -> None`:
     - `ContinuitySceneStarted`: reset the two accumulator strings, set
       `_continuity_display_scene_id = event.scene_id`; if it equals
       `self.current_scene_id`, clear `continuity_snapshot_view` and
       `continuity_snapshot_reasoning_view`.
     - `ContinuityContentDelta`: append to `_continuity_content_text`; if
       `_continuity_display_scene_id == self.current_scene_id`, `setPlainText`
       into `continuity_snapshot_view` and schedule scroll-to-end.
     - `ContinuityReasoningDelta`: same, into
       `continuity_snapshot_reasoning_view` (content and reasoning are routed
       to their own tabs live, since continuity already has two distinct
       destinations — unlike the Prose tab, which has no live-visible split
       and only separates body/reasoning after persistence).
     - `ContinuitySceneComplete`/anything else: no-op; final display still
       comes from `_refresh()` in `_on_continuity_task_finished`, unchanged.
   - Add `_schedule_scroll_continuity_to_end`/`_scroll_continuity_to_end` and
     the reasoning-tab equivalents, mirroring
     `_schedule_scroll_body_to_end`/`_scroll_body_to_end`.
   - Reset the three new accumulator fields in `_on_continuity_task_finished`
     alongside its existing thread teardown.

3. **Tests**:
   - `test/scene/agent/test_continuity.py`: add a `script_stream` helper
     mirroring `test_rendering.py`'s (fake chunk/choice/delta classes), and
     port `test_stream_render_*`'s cases to `stream_continuity_edit`. Add
     tests for `stream_accept_scene` (yields `ContinuitySceneStarted`, then
     deltas, then `ContinuitySceneComplete`; persists identically to
     `accept_scene`) and `stream_regenerate_snapshots_from` (one
     started/complete pair per scene at/after `from_position`, stops at the
     first unrendered scene — mirroring the existing
     `regenerate_snapshots_from` tests).
   - `test/scene/gui/test_rendering_column.py`: convert the tests that
     currently monkeypatch `rendering_column_module.accept_scene` /
     `regenerate_snapshots_from` (`test_generate_accepts_scene_and_updates_continuity_tab`,
     `test_generate_skips_accept_scene_without_continuity_config`,
     `test_generate_shows_continuity_notice_when_accept_scene_fails`,
     `test_activate_version_calls_regenerate_snapshots_and_updates_tab`,
     `test_activate_version_shows_continuity_notice_when_regenerate_fails`,
     `test_buttons_stay_blocked_while_continuity_task_runs_after_generation`,
     `test_cancel_prevents_continuity_task_from_starting`) to instead
     monkeypatch `stream_accept_scene`/`stream_regenerate_snapshots_from`
     with fake generators yielding the same event shapes (mirroring the
     existing `_fake_stream` helper for `stream_render`), persisting via
     `create_snapshot` on their fake `ContinuitySceneComplete` the same way
     the current fakes do. Add new tests asserting: content and reasoning
     deltas progressively appear in `continuity_snapshot_view`/
     `continuity_snapshot_reasoning_view` before the task finishes (gated
     with a `threading.Event`, mirroring `test_cancel_prevents_continuity_task_from_starting`);
     scroll-to-end fires on the continuity tab as it streams (mirroring
     `test_body_view_scrolls_to_end_as_content_streams`); and that during a
     `regenerate_snapshots_from` chain, deltas for a scene other than the
     currently-selected one do not appear in the visible tabs.

## Verification

- `pdm run lint` passes with no errors.
- `pdm run pytest` passes in full, including the new and converted tests
  above, with the usual HTML coverage report generated.

## Log

### Review - 2026-08-29T22:41:47Z - John Hoff

This scripted encounter's Plan is well-grounded in the existing codebase (verified `stream_render`/`_RenderWorker` patterns in `rendering.py`/`rendering_column.py` that it mirrors for continuity streaming) and satisfies both applicable lore items: its Verification section explicitly requires `pdm run lint` to pass cleanly, and its test plan adds/converts coverage in `test/scene/agent/test_continuity.py` and `test/scene/gui/test_rendering_column.py`, correctly mirroring the modified `src/scene/agent/continuity.py` and `src/scene/gui/rendering_column.py` paths with the standard `pdm run pytest` HTML-coverage verification. No lore conflicts or gaps were found, and no concerns are flagged as unverifiable.

### Message - 2026-08-29T23:32:04Z - John Hoff

Two deviations from the original Plan during implementation, both requested by the user: (1) `_on_continuity_event` streams content and reasoning deltas together into a single combined live view in the Continuity Snapshot tab, matching exactly how the Prose tab handles rendering's unsplit stream, rather than the originally planned live split into separate Continuity Snapshot / Continuity Snapshot Reasoning tabs -- the reasoning tab is now only updated by the post-completion `_refresh()`, same as Prose Reasoning. This also required adding a scroll-to-end call after that final `_refresh()` in `_on_continuity_task_finished`, since persisting the snapshot mid-generator (inside `stream_accept_scene`) creates a timing gap not present in the render path, which could otherwise race the last streamed delta's deferred scroll ahead of the final refresh's scroll-position-resetting `setPlainText`. (2) Body Reasoning, Continuity Snapshot, and Continuity Snapshot Reasoning tabs now share the same scaled-up font as the Prose tab (`BODY_FONT_SCALE`), for visual consistency across all four tabs.

### Completed - 2026-08-29T23:36:25Z - John Hoff

Implemented: `stream_continuity_edit`/`stream_accept_scene`/`stream_regenerate_snapshots_from` in `src/scene/agent/continuity.py` mirror `stream_render`'s generator pattern, streaming into the GUI's Continuity Snapshot tab via a reworked `_ContinuityWorker` (added `event_received` signal) and `_on_continuity_event` in `src/scene/gui/rendering_column.py`. Per user direction during implementation, content and reasoning deltas stream combined into the single Continuity Snapshot tab (matching Prose's unsplit live stream) rather than split live across the two continuity tabs, with the reasoning tab populated only by the post-completion `_refresh()`; a scroll-to-end race exposed by mid-generator persistence was fixed with an extra scheduled scroll after that refresh. Also matched the Prose tab's scaled-up font across Prose Reasoning, Continuity Snapshot, and Continuity Snapshot Reasoning. `pdm run lint` clean; `pdm run pytest` passes in full (523 tests).
