---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-30T15:17:09Z'
depends_on: []
kind: unscripted
name: e012-continuity-test-race-fix
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-30T15:46:47Z'
---

## Requirements

Fixed a flaky assertion in `test/scene/gui/test_rendering_column.py`'s
`test_buttons_stay_blocked_while_continuity_task_runs_after_generation` (added in
e004-continuity-task-race-guard). The test spins up a real background `QThread` running a
`threading.Event`-gated fake `stream_accept_scene`, then clicked `activate_button` and
immediately asserted `accept_calls == [scene_id]` with no synchronization — `QThread.start()` is
fire-and-forget, so nothing guaranteed the worker thread had actually reached
`accept_calls.append(...)` by the time the main thread's assertion ran. This passed reliably in
isolation but failed intermittently inside the full `pdm run pytest` run (observed once during
e011-full-story-view-and-save's verification, then passed on an isolated re-run), consistent with
OS thread-scheduling pressure under the full suite's added contention.

Added `qtbot.waitUntil(lambda: accept_calls == [scene_id], timeout=2000)` immediately before the
existing `continuity_thread = widget._continuity_thread` / `activate_button.click()` /
`accept_calls` assertions, so the test waits for the continuity worker thread to actually reach
that point instead of sampling it at an arbitrary moment. No production code changed — the
`_continuity_busy` re-entrancy guard this test protects was already correct; only the test's
cross-thread synchronization was at fault.

Verified with 5 consecutive isolated runs of the single test, plus three full-suite runs (with and
without coverage instrumentation, matching the conditions of the original intermittent failure) —
all green, 547/547. `pdm run lint` clean.

## Rationale

This test is the only regression coverage for a real, previously-shipped crash
("QThread: Destroyed while thread is still running", fixed in e004-continuity-task-race-guard) —
deleting it on account of flakiness would silently drop that protection. The flakiness had a
concrete, fixable root cause in the test itself (a missing wait across a genuine thread boundary),
not in the production code or in the test's premise, so fixing the synchronization was the right
call over removing or loosening the test.

## Log

### Review - 2026-08-30T15:20:01Z - John Hoff

Verified the described fix in test/scene/gui/test_rendering_column.py: the qtbot.waitUntil(lambda: accept_calls == [scene_id], timeout=2000) synchronization point is present exactly where described, immediately before the continuity_thread capture, activate_button.click(), and the accept_calls assertion in test_buttons_stay_blocked_while_continuity_task_runs_after_generation. The change is a narrowly-scoped, sound fix for a genuine unsynchronized cross-thread read (not a loosening of the regression coverage it protects), touches no production code, and stays within the mirrored test/ path convention. Lines added are well within the 120-char limit and the encounter's reported lint/full-suite results are consistent with the linting and unit-testing lore. No conflicts found; passes with notes.

### Completed - 2026-08-30T15:46:47Z - John Hoff

Confirmed recorded Requirements/Rationale still accurate; no follow-up actions raised by the review. The qtbot.waitUntil synchronization fix is in place, verified stable across 5 isolated runs and 3 full-suite runs (with and without coverage), and pdm run lint is clean.
