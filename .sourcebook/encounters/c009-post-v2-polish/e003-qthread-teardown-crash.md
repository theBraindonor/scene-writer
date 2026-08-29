---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-29T03:22:44Z'
depends_on: []
kind: scripted
name: e003-qthread-teardown-crash
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-29T03:37:43Z'
---

# Fix QThread crash caused by deleteLater()-chain teardown

## Requirements

- Fix a reproducible crash where the app dies with "QThread: Destroyed
  while thread '' is still running" (and can terminate the process) during
  ordinary use — no window close, cancel, or scene switch required; it can
  happen from a single generation followed by any further activity that
  triggers Python's cyclic garbage collector while the previous background
  thread is still finishing its own shutdown.
- Root cause: each of the three background-thread call sites tears down its
  `QThread`/worker via a `finished.connect(deleteLater)` chain, including a
  self-referential connection (`thread.finished.connect(thread.deleteLater)`).
  That connection makes the `QThread` hold a bound method that references
  itself, forming a Python reference cycle. A cycle can only be freed by
  Python's cyclic garbage collector, which can run at an arbitrary,
  GC-threshold-driven moment — including while the thread's own event loop
  is still processing its queued `quit()` and hasn't actually stopped yet.
  If the cyclic collector frees the `QThread` at that moment, it destroys
  the underlying C++ thread object while the OS thread is still running,
  which is exactly the reported crash.
- Fix all three affected call sites by replacing the `deleteLater()`-chain
  teardown with an explicit, synchronous `self._thread.quit()` followed by
  `self._thread.wait()` inside each `finished` handler, before any other
  work in that handler runs. By the time a `finished` handler is invoked,
  the worker's `run()` has already returned, so `quit()` + `wait()` return
  immediately (no perceptible UI stall) while guaranteeing `isRunning()` is
  `False` before the `QThread`/worker objects can ever be garbage collected
  — deterministic, and no longer dependent on cyclic-GC timing:
  - `ChatPanel._start_worker` / `ChatPanel._on_worker_finished`
    (`src/scene/gui/chat_panel.py`)
  - `RenderingColumn._start_generation` / `RenderingColumn._on_generation_finished`
    (`src/scene/gui/rendering_column.py`)
  - `RenderingColumn._start_continuity_task` / `RenderingColumn._on_continuity_task_finished`
    (`src/scene/gui/rendering_column.py`)
- Remove the now-unneeded `worker.finished.connect(thread.quit)`,
  `worker.finished.connect(worker.deleteLater)`, and
  `thread.finished.connect(thread.deleteLater)` connections at each site —
  the explicit `quit()`/`wait()` call in the finished handler replaces all
  three, and plain Python reference counting (no remaining cycle) cleans up
  the `QThread`/worker objects once the site's `self._thread`/`self._worker`
  (or the continuity task's local `thread`/`worker`) are reassigned by the
  next call, or the owning widget is destroyed.
- No behavior change to what each worker does, what signals it emits, or
  when `_on_*_finished` performs its existing post-processing (saving the
  rendering, refreshing the UI, starting the continuity task, etc.) — only
  the thread-teardown mechanism changes, at the very top of each `finished`
  handler.
- This is a targeted lifecycle fix. It does not add a `MainWindow.closeEvent`
  guard or any other close-time protection — that was an earlier, wrong
  hypothesis for this same symptom (the crash reproduces with the app
  staying open the whole time, confirmed by the reporter) and is out of
  scope here; if closing mid-generation turns out to need its own guard,
  that would be a separate, later encounter based on its own evidence.

## Rationale

The user reported "QThread: Destroyed while thread '' is still running"
crashing the app during ordinary use (not while closing the window, not
while cancelling — "just generating normally"). An initial hypothesis
blaming this on closing the app mid-generation was wrong, per the user's
correction, and is explicitly not addressed here.

The actual root cause was confirmed by reproduction, not inferred from code
reading alone: a minimal PySide6 script reproducing the exact
`moveToThread` + `started.connect(worker.run)` +
`finished.connect(thread.quit)` + `finished.connect(*.deleteLater)` pattern
used at all three call sites crashed silently (no traceback, process exit)
after a single generate-cycle, 3/3 runs, purely from repeatedly
starting/finishing threads with normal per-cycle object churn (simulating
the DB writes and UI refresh `_on_generation_finished` already does) —
with no window close, cancel, or user interaction involved. Replacing the
`deleteLater()`-chain teardown with an explicit `thread.quit()` +
`thread.wait()` in the finished handler, and removing the
self-referential/cross `deleteLater()` connections, ran 20 cycles cleanly
every time under the same stress. This isolates the `deleteLater()`-chain
teardown itself (specifically its self-referential connection creating a
Python-GC-timing-dependent reference cycle) as the cause, independent of
anything else in the app, and confirms the fix.

## Plan

1. In `src/scene/gui/chat_panel.py`'s `_start_worker`, remove
   `self._worker.finished.connect(self._thread.quit)`,
   `self._worker.finished.connect(self._worker.deleteLater)`, and
   `self._thread.finished.connect(self._thread.deleteLater)`. Keep
   `self._thread.started.connect(self._worker.run)`,
   `self._worker.event_received.connect(self._on_turn_event)`, and
   `self._worker.finished.connect(self._on_worker_finished)`.
2. At the top of `ChatPanel._on_worker_finished`, add
   `self._thread.quit()` followed by `self._thread.wait()`, with a short
   comment explaining why (worker.run() has already returned by the time
   this handler fires, so this stops the thread's event loop
   deterministically instead of relying on a `deleteLater()` chain whose
   timing depends on Python's cyclic garbage collector). Leave the rest of
   the handler's existing behavior unchanged.
3. Apply the same two changes to `src/scene/gui/rendering_column.py`'s
   `_start_generation`/`_on_generation_finished` pair. Update the existing
   comment block in `_on_generation_finished` (currently explaining why
   `self._thread`/`self._worker` are deliberately left alone) to reflect
   the new deterministic-wait rationale instead of the old
   leave-alone-until-overwritten rationale, since that reasoning no longer
   applies once teardown is synchronous.
4. Apply the same two changes to the continuity task pair,
   `_start_continuity_task`/`_on_continuity_task_finished`, using the
   locally-scoped `thread`/`worker` names as they exist today (assigned to
   `self._continuity_thread`/`self._continuity_worker`). Update that
   method's existing comment similarly.
5. Check `test/scene/gui/test_chat_panel.py` and
   `test/scene/gui/test_rendering_column.py` (if they exist and cover
   `_start_worker`/`_start_generation`/`_start_continuity_task` or their
   `_on_*_finished` handlers) for any assertion tied to the removed
   `deleteLater`/`quit` connections or to `QThread`/worker mocking that the
   new `quit()`/`wait()` calls would break, and update as needed. If real
   `QThread`s are exercised in tests, confirm `wait()` does not hang test
   runs (workers under test complete near-instantly, so this should be a
   no-op wait).
6. Run `pdm run lint` and `pdm run pytest`, fixing anything flagged.

## Verification

- `pdm run lint` passes with no errors.
- `pdm run pytest` passes, including any GUI thread-related tests and the
  full existing suite.
- Re-run the reproduction script's stress pattern (starting/finishing many
  cycles of a `QThread`+worker pair using the new
  `quit()`+`wait()`-in-finished-handler pattern, with the same per-cycle
  object churn as before) to confirm no crash across at least 20 cycles,
  matching the fix already validated during investigation.
- Manually run the app (`pdm run scene-writer`) and generate a scene (and,
  if a continuity model is configured, let the continuity editor run
  immediately after) several times in a row under normal use — no window
  closing, no cancelling — to confirm no crash and no
  "QThread: Destroyed while thread" warning in the console.
- `git grep -n "deleteLater" src/scene/gui/chat_panel.py
  src/scene/gui/rendering_column.py` shows no remaining
  `finished.connect(...deleteLater)` wiring at the three fixed call sites.

## Log

### Review - 2026-08-29T03:27:47Z - John Hoff

This scripted encounter's Plan is well-grounded: it accurately describes the existing self-referential finished.connect(deleteLater) teardown chain at all three named call sites in chat_panel.py and rendering_column.py (verified directly against the current source), proposes a standard, low-risk fix (synchronous thread.quit()+thread.wait() in each finished handler, replacing the GC-timing-dependent chain), and satisfies both applicable lore items — linting (Plan step 6, Verification) and unit-testing (Plan step 5 reviews existing tests for breakage and requires pdm run pytest to pass, and the modified handlers are already exercised by the existing functional test suite). The one soft gap is that Plan step 5 asks only to check for breakage in existing tests rather than to add a new assertion that directly verifies the fix's core claim (deterministic thread-stopped-by-return guarantee), and it doesn't explicitly flag that test_rendering_column.py's wait_for_worker_thread_to_finish helper docstring will become stale once the old deferred-cleanup behavior is gone — neither rises to a lore conflict, so this passes with those two notes for the implementer to consider.

### Completed - 2026-08-29T03:37:43Z - John Hoff

Implemented as planned at all three call sites (ChatPanel._start_worker/_on_worker_finished, RenderingColumn._start_generation/_on_generation_finished, RenderingColumn._start_continuity_task/_on_continuity_task_finished): removed the deleteLater()-chain teardown and replaced it with an explicit self._thread.quit()/self._thread.wait() at the top of each finished handler, with a comment explaining why. Also removed test/scene/gui/test_rendering_column.py's now-obsolete wait_for_worker_thread_to_finish helper and its 10 call sites, since the thread is guaranteed stopped before generation_finished/turn_completed fires; restored one incidental qtbot.wait(10) in test_body_view_scrolls_to_end_as_content_streams with an accurate comment, since that test relied on the removed helper's side effect of pumping the event loop for an unrelated deferred QTimer.singleShot scroll callback. 487 tests pass, lint is clean. Re-validated the fix against the real RenderingColumn class (not just the isolated reproduction) with a 30-cycle generate-stress script hitting an on-disk SQLite scratch DB and forcing gc.collect() each cycle — no crash, no QThread warning, versus a hard crash after 1 cycle previously with the old teardown pattern.
