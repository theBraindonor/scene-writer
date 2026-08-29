---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-29T19:53:22Z'
depends_on: []
kind: scripted
name: e004-continuity-task-race-guard
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-29T20:48:21Z'
---

# Fix continuity-task re-entrancy race and add render/continuity progress feedback

## Requirements

- Fix a reproducible crash — `QThread: Destroyed while thread '' is still
  running` — that occurs during ordinary sequential scene rendering when
  continuity is configured, with no cancel/close/manual Activate click
  required. Confirmed via terminal output and by the affected scene's
  continuity snapshot being left unwritten ("not filled out") after the
  crash.
- Root cause: `RenderingColumn._start_continuity_task`
  (`src/scene/gui/rendering_column.py`) has no guard against being invoked
  while a previously-started continuity task (`self._continuity_thread`/
  `self._continuity_worker`) is still running. `_refresh()`'s existing
  `busy` computation only considers `self._generating`, so the Generate
  button — and via `_on_activate_clicked`, the Activate button — re-enable
  immediately once a render finishes, even though the continuity task it
  just kicked off (`accept_scene`, which can involve its own LLM round
  trip and, with a slower continuity model than the render model, can
  outlast the next render) is still in flight. Rendering and completing a
  second scene before the first scene's continuity task returns causes
  `_on_generation_finished` to call `_start_continuity_task` again, which
  unconditionally overwrites `self._continuity_thread`/`self._continuity_worker`
  while the prior `QThread` is still executing. That orphaned `QThread`
  object loses its only Python reference and is later destroyed by
  Python's garbage collector while its OS thread is still running — the
  exact "QThread: Destroyed while thread" crash `e003` fixed for
  `deleteLater()`-based teardown, resurfacing here via a different path:
  premature loss-of-reference rather than a GC-timing-dependent cycle.
- Close the race by disabling the controls that can start a new render or
  continuity task — `generate_button`, `activate_button`, and
  `delete_button` — for as long as *either* the render worker or the
  continuity worker is active, not just the render worker as today. This
  structurally prevents `_start_continuity_task` from ever being called a
  second time before `_on_continuity_task_finished` has run its existing
  `quit()`/`wait()` teardown on the prior continuity thread.
- Add visible stage feedback next to the generate/cancel controls, below
  the rendered-text tabs, so it's possible to tell from the UI whether a
  continuity task is still running rather than having to guess: show
  "Rendering scene prose..." while the render is streaming, updating to
  "Rendering scene prose... Done." once it completes; if a continuity
  task then starts, update to "Creating continuity snapshot...", then
  "Creating continuity snapshot... Done." once it finishes. The label
  persists showing its last state (it does not auto-hide) until the next
  render begins, so the "still working" vs. "done" state is visible at a
  glance at any time — this is also the primary manual verification
  signal for confirming the continuity phase actually completed.
- No change to what either worker does, what signals it emits, or the
  substance of the existing `quit()`/`wait()` teardown from `e003` — this
  is additive UI-state gating plus a status label, not a change to the
  threading/signal architecture itself.

## Rationale

The user reproduced this by pointing the render step at a fast OpenRouter
model while the continuity model stays comparatively slow, so a render
completes (and its continuity task starts) well before the *previous*
scene's continuity task has finished — a timing gap that's easy to hit in
normal generate-scene-after-scene use, not an edge case requiring manual
Activate clicks. The `QThread: Destroyed while thread '' is still running`
terminal message, together with the crashing scene's continuity snapshot
being unfilled, pinpoints the continuity `QThread` specifically (not the
render one, which `e003` already made safe) as the object being destroyed
mid-run.

Disabling Generate/Activate/Delete while continuity is busy is both the
fix (it removes the only two call sites, `_on_generation_finished` and
`_on_activate_clicked`, that can re-invoke `_start_continuity_task` while
one is already in flight) and, combined with the new stage label, the
user's requested guard-plus-feedback: a guard that prevents the crash, and
visible confirmation of which phase is in progress so it's no longer a
guessing game whether continuity is still running.

## Plan

1. In `RenderingColumn.__init__` (`src/scene/gui/rendering_column.py`),
   add `self._continuity_busy: bool = False` alongside the existing
   `self._generating`/`self._generating_scene_id` state, and add
   `self.progress_label = QLabel()` (word-wrap on, hidden initially).
   Insert it as the first widget in `generate_row` (before the
   `addStretch()`), so it renders to the left of the preview-prompt
   checkbox and Generate/Cancel buttons, on the row directly under
   `self.tabs`.
2. In `_refresh()`, change `busy = self._generating` to
   `busy = self._generating or self._continuity_busy`, so
   `activate_button`/`delete_button` and the generate/cancel row all stay
   gated on continuity too.
3. In `_start_generation`, show the label:
   `self.progress_label.setText("Rendering scene prose...")` / `.show()`.
4. In `_on_generation_finished`, after the existing render-thread
   `quit()`/`wait()` and before deciding whether to start a continuity
   task: if the render succeeded (not error, not cancelled — reuse the
   existing `error_message`/`was_cancelled` locals already computed
   there), set the label to `"Rendering scene prose... Done."`; on error
   or cancellation, hide `progress_label` instead (the existing
   `notice_label` already surfaces that outcome, so the two don't need to
   duplicate each other).
5. Still in `_on_generation_finished`, when a continuity task is actually
   started (`self._continuity_config is not None and generated_scene is
   not None`), set `self._continuity_busy = True` before calling
   `_start_continuity_task`, and update the label to
   `"Creating continuity snapshot..."` at the top of
   `_start_continuity_task` (shared by both call sites — generation and
   `_on_activate_clicked`'s `regenerate_snapshots_from` path — so it
   applies uniformly rather than being written twice).
6. In `_on_continuity_task_finished`, after the existing
   `self._continuity_thread.quit()`/`.wait()`, set
   `self._continuity_busy = False` and update the label to
   `"Creating continuity snapshot... Done."`, then call the existing
   `self._refresh_continuity_snapshot()` and (new) `self._refresh()` so
   the now-unblocked Generate/Activate/Delete buttons re-enable
   immediately rather than waiting for some other trigger.
7. Run `pdm run lint` and `pdm run pytest`, fixing anything flagged.

## Verification

- `pdm run lint` passes with no errors.
- `pdm run pytest` passes, including the existing
  `test/scene/gui/test_rendering_column.py` suite; add or update test
  coverage asserting: (a) `activate_button`/`generate_button` stay
  disabled while `_continuity_busy` is `True`, even after a render's
  `finished` signal has fired; (b) a second `_start_continuity_task` call
  cannot occur — directly or via a second simulated `_on_generate_clicked`/
  `_on_activate_clicked` — while `self._continuity_thread` is still
  running, i.e. `self._continuity_thread`/`self._continuity_worker` are
  never overwritten before `_on_continuity_task_finished` has run.
- Manually run the app (`pdm run scene-writer`) configured with a fast
  render model and a slower continuity model (reproducing the user's
  original setup), and generate several scenes back-to-back without
  waiting for each one's continuity phase to finish on its own — confirm
  Generate/Activate/Delete stay disabled, the progress label correctly
  cycles through "Rendering scene prose..." → "...Done." →
  "Creating continuity snapshot..." → "...Done." for each scene in turn,
  and there is no "QThread: Destroyed while thread" message and no crash
  across at least 10 scenes generated back-to-back.

## Log

### Review - 2026-08-29T19:55:47Z - John Hoff

Reviewed e004-continuity-task-race-guard against the two applicable world lore items, linting and unit-testing, and against the actual state of src/scene/gui/rendering_column.py (within the assigned gui region) and its existing test file test/scene/gui/test_rendering_column.py. The Plan's root-cause diagnosis is accurate — _refresh()'s busy flag at line 338 currently considers only self._generating, and _start_continuity_task (lines 607-617) unconditionally clobbers self._continuity_thread/self._continuity_worker with no in-flight check, reachable from both _on_generation_finished and _on_activate_clicked — and the proposed fix (a self._continuity_busy flag folded into busy, plus a persistent stage label) maps cleanly onto the real widget layout with no invented structure. Both lore items are explicitly satisfied: the Plan and Verification require pdm run lint to pass with zero errors, and pdm run pytest to pass with new/updated coverage in the correctly-mirrored existing test file, addressing the two specific race conditions being closed. No other lore applied to this encounter/region, and nothing needed to be flagged as out of scope. Verdict: PASS-WITH-NOTES.

### Message - 2026-08-29T20:03:38Z - John Hoff

Additional testing finding, deviation from the reviewed Plan: clicking Cancel while a render is streaming does not stop continuity from starting. _on_generation_finished's continuity-start condition (currently `if self._continuity_config is not None and generated_scene is not None:`) does not check `was_cancelled`, so if any partial content had already streamed in before cancel took effect, `_start_continuity_task` still fires for that cancelled rendering. Fix: add `and not was_cancelled` to that condition (Plan step 5), so Cancel halts everything - no continuity task starts on a cancelled render - not just the render itself. This does not change the existing, intentional partial-content-still-saved-to-SQLite behavior on cancel, which is unrelated. Verification gains one more manual check: click Cancel mid-render with continuity configured and confirm no continuity task starts (progress label never shows "Creating continuity snapshot...", self._continuity_busy stays False, self._continuity_thread/_continuity_worker stay unset for that render).

### Completed - 2026-08-29T20:48:21Z - John Hoff

Implemented as planned, plus the recorded cancel-halts-continuity deviation, in src/scene/gui/rendering_column.py: added self._continuity_busy and a persistent progress_label (left of the Generate/Cancel row) cycling "Rendering scene prose..." -> "...Done." -> "Creating continuity snapshot..." -> "...Done."; _refresh() now gates Generate/Activate/Delete on self._generating or self._continuity_busy, structurally preventing _start_continuity_task from ever being re-entered while a prior continuity QThread is still running; _on_generation_finished's continuity-start condition gained "and not was_cancelled" so Cancel halts everything, matching the deviation logged 2026-08-29. Added two tests to test/scene/gui/test_rendering_column.py covering the exact scenarios: buttons staying blocked (and no second continuity task starting) while a continuity task outlasts its render, and Cancel preventing accept_scene from ever being called. pdm run lint is clean; pdm run pytest passes 512/512. The Verification section's manual real-model back-to-back-scene run (fast render model / slow continuity model, 10+ scenes, watching for the QThread warning) was not performed in this environment (no OpenRouter credentials here) - the user will confirm that pass themselves before relying on it in production use.
