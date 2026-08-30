---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-30T16:03:28Z'
depends_on: []
kind: scripted
name: e013-render-full-story
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-30T16:50:05Z'
---

## Requirements

Add **Render Full Story...** as a new action at the *top* of the GUI's `Render` menu
(`src/scene/gui/main_window.py`), above `View Full Story...` and `Save Full Story...`:

- On click, if no story is selected, show an informational message and do nothing. If the
  selected story has no scenes, show an informational message and do nothing. If rendering isn't
  configured (no rendering LLM available), show an informational message and do nothing.
- Otherwise show a confirmation dialog with **Proceed** and **Cancel** buttons (mirroring
  `RenderingColumn`'s existing `_PromptPreviewDialog` button convention), explaining that this
  will render every scene in the story and replace each one's active rendering. Cancel does
  nothing further.
- On Proceed, render every scene in the story, one at a time, in position order, each becoming
  the scene's new active rendering — reusing the exact same single-scene generation pipeline
  `RenderingColumn`'s own Generate button drives (including its automatic continuity-snapshot
  step), scene by scene, without opening the Preview Prompt dialog at any point.
- The user must be able to **watch it happen**: as each scene renders, the GUI actually selects
  that scene (so the Scenes tab and the Rendering column both visibly update and stream exactly
  as they would for a manual single-scene render) — this is not a background/headless batch job.
- The existing **Cancel** button in the Rendering column must halt the *entire* run, not just the
  in-progress scene: once clicked, no further scene is started. The in-progress scene's partial
  text is still saved as a new version and made active, identical to today's single-scene Cancel
  behavior (deliberately unchanged) — this covers the "model won't stop generating" failure mode
  named in Rationale below, where the user (not the app) recognizes runaway/repeating output and
  cancels it manually.
- If a scene's generation errors out, the run stops the same way (no further scenes started).
- While a run is in progress, the `Render Full Story...` menu action is disabled (re-enabled once
  the run ends, however it ends) so it can't be re-triggered on top of itself.

## Rationale

The user wants a one-click way to (re-)render an entire story end to end instead of stepping
through every scene by hand, but with two hard constraints:

1. **Visibility.** They explicitly want to *see* each scene rendering as it happens, not just get
   a finished result — so this reuses the real `RenderingColumn` UI scene-by-scene rather than
   driving generation headlessly and updating the screen only at the end.
2. **A reliable stop.** With custom-tuned/smaller roleplay models, a known failure mode is a
   stream that never naturally terminates — it keeps emitting varying-length repeated text
   indefinitely. This is a live-content problem, not a stalled/idle connection, so a request
   timeout would not help (chunks keep arriving; there's nothing to time out) and reliably
   *detecting* it automatically is considered impractical. The only dependable stop is the human
   noticing and clicking Cancel — so Cancel must be guaranteed to halt the whole batch, not just
   let it silently move on to the next scene while the bad one sits mid-stream. The existing
   cooperative cancel already interrupts an actively-streaming scene promptly (the flag is
   rechecked between chunks, and chunks keep arriving even in the runaway case) — the missing
   piece is solely that today's Cancel has no notion of "and stop the batch too."

Given the confirmed decision to leave single-scene Cancel's save/activate semantics untouched
even inside a batch run, the whole feature can be built by *driving* `RenderingColumn`'s existing
generate/cancel/continuity machinery from a small external controller, rather than duplicating or
forking any of that logic. Concretely:

- `RenderingColumn._on_generate_clicked` already does two things worth separating: (a) guard
  checks + building the render messages, and (b) the Preview Prompt gate before actually
  starting. Extracting (a) into a shared helper lets a new `generate_now()` method start
  generation immediately, skipping the Preview Prompt dialog (which would otherwise pop up and
  block on every single scene of an unattended run, defeating the point).
- The controller needs to know when a scene is *fully* done (render **and**, if configured, its
  follow-on continuity snapshot) before advancing — firing on the render's own completion alone
  would run ahead of continuity and degrade later scenes' "Current Canon" context. Rather than
  overload the existing `generation_finished` signal (already relied on elsewhere with its
  current, render-only-complete timing), a new `scene_settled` signal is added, emitted once
  after either path (no continuity task started this round, or the continuity task finishes).
  Two small instance attributes (`last_generation_cancelled`, `last_generation_error`) record the
  outcome so the controller can tell success from cancel/error without changing any existing
  signal's payload.
- The controller selects each scene through the *real* `ScenesWidget.list_widget` (searching by
  scene id rather than assuming row-index continuity, so it isn't thrown off by the list being
  refreshed) so the existing `scene_selected` -> `EntityColumn.current_scene_changed` ->
  `RenderingColumn.set_scene` cascade drives the visible update, exactly as a manual click would.
- If the active story changes out from under the controller mid-run (e.g. the user opens a
  different story via File > Open Story while a batch is in progress), the controller detects
  that at its next checkpoint and stops rather than continuing to drive scene selection against
  what is now a different story's list.
- An empty/no-content generation outcome (no error, not cancelled, but the model returned
  nothing) is treated as a success and the run advances anyway — deliberately not tracked as a
  fourth stop condition, since it is exceedingly rare, does not crash anything downstream (missing
  "recent prose"/"current canon" sections are simply omitted for the next scene), and adding a
  third `last_generation_*` flag for it was judged not worth the extra surface for how unlikely it
  is to occur.

## Plan

1. `src/scene/gui/rendering_column.py`:
   - Add `scene_settled = Signal()` to `RenderingColumn`, plus `self.last_generation_cancelled:
     bool = False` and `self.last_generation_error: str | None = None`, initialized in
     `__init__`.
   - Extract the guard-checks-and-message-building portion of `_on_generate_clicked` (the
     `current_scene_id`/`current_story_id`/`llm_config`/`_generating` checks, `build_render_messages`
     call with its `ValueError` handling, and `_hide_notice()`) into a new private helper, e.g.
     `_build_messages_or_notify() -> list[dict] | None`. `_on_generate_clicked` becomes: call the
     helper; if `None`, return; otherwise run the existing Preview Prompt gate; then
     `_start_generation(messages)`.
   - Add a new public method `generate_now(self) -> bool`: calls `_build_messages_or_notify()`;
     if `None`, return `False`; otherwise call `_start_generation(messages)` directly (bypassing
     the Preview Prompt dialog entirely) and return `True`.
   - In `_on_generation_finished`, right after computing the existing `was_cancelled`/
     `error_message` locals, set `self.last_generation_cancelled = was_cancelled` and
     `self.last_generation_error = error_message`. Track a local `continuity_started = False`,
     set `True` at the same point `_start_continuity_task` is called for this generation. After
     the existing `self.generation_finished.emit()` at the end of the method, add: `if not
     continuity_started: self.scene_settled.emit()`.
   - At the end of `_on_continuity_task_finished` (after its existing final scroll scheduling),
     add `self.scene_settled.emit()`.

2. Add `src/scene/gui/full_story_render.py`:
   - `RenderFullStoryConfirmDialog(QDialog)` — modal, title "Render Full Story", a word-wrapped
     `QLabel` explaining the effect (renders every scene, replacing each one's active rendering),
     and a bottom button row with **Cancel** then **Proceed** (mirroring
     `RenderingColumn._PromptPreviewDialog`'s exact button order/semantics: Cancel ->
     `self.reject()`, Proceed -> `self.accept()`).
   - `FullStoryRenderController(QObject)`: takes the owning `MainWindow` in its constructor.
     - `start(self, story_id: int) -> None`: loads `list_scenes(session, story_id)` ids (position
       order) into `self._scene_ids`, resets `self._index = 0`, records `self._story_id =
       story_id`, connects to `rendering_column.scene_settled`, and calls `self._advance()`.
     - `_advance(self) -> None`: if `self._main_window.current_story_id != self._story_id` or
       `self._index >= len(self._scene_ids)`, call `self._finish()`. Otherwise look up
       `self._scene_ids[self._index]` in `entity_column.scenes.list_widget` by its stored
       `Qt.ItemDataRole.UserRole` id (not by row-index assumption), `setCurrentRow(...)` on the
       matching row (or `self._finish()` if not found, e.g. the scene was deleted mid-run), then
       call `rendering_column.generate_now()`. If that returns `False` (couldn't start), call
       `self._finish()`.
     - Connected to `scene_settled`: if `rendering_column.last_generation_cancelled` or
       `rendering_column.last_generation_error is not None`, call `self._finish()`; otherwise
       increment `self._index` and call `self._advance()` again.
     - `_finish(self) -> None`: disconnects from `scene_settled` and emits a `finished = Signal()`
       exactly once.
   - At the start of `start()`, also switch `entity_column.tabs` to its "Scenes" tab (found by
     matching `tabText`, not a hardcoded index) so the scene-by-scene selection is visible without
     the user needing to click over to it first.

3. `src/scene/gui/main_window.py`:
   - Import `FullStoryRenderController` and `RenderFullStoryConfirmDialog` from
     `scene.gui.full_story_render`, and `list_scenes` from `scene.core.scene`.
   - In `_build_menu_bar`, add `&Render Full Story...` as the *first* action under the `Render`
     menu (before `View Full Story...`), wired to a new `_on_render_full_story` handler. Keep a
     reference to the action (e.g. `self.render_full_story_action`) so it can be disabled/re-enabled.
   - `_on_render_full_story`:
     - No story selected -> `QMessageBox.information(self, "Render Full Story", "Select a story
       first.")` (reusing the existing `NO_STORY_SELECTED_FOR_RENDER_TEXT` constant) and return.
     - No scenes in the story (`list_scenes(session, story_id)` empty) -> an informational message
       ("This story has no scenes.") and return.
     - `self.rendering_column._llm_config is None` -> an informational message ("Rendering is not
       configured. See the Rendering panel for details.") and return.
     - Otherwise show `RenderFullStoryConfirmDialog`; if not accepted, return.
     - Disable `self.render_full_story_action`. Create `FullStoryRenderController(self)`, connect
       its `finished` signal to re-enable the action (and drop the reference), then call
       `.start(self.current_story_id)`.

4. Tests:
   - `test/scene/gui/test_rendering_column.py`: new tests for `scene_settled` firing once with no
     continuity configured, once cancelled (no continuity started), and once after continuity
     finishes on a successful generation; for `generate_now()` bypassing the Preview Prompt dialog
     even when its checkbox is checked; and for `last_generation_cancelled`/`last_generation_error`
     reflecting cancel/error/success outcomes correctly.
   - New `test/scene/gui/test_full_story_render.py`: `RenderFullStoryConfirmDialog`'s Cancel/Proceed
     buttons reject/accept; `FullStoryRenderController` renders a multi-scene story's scenes in
     position order (each scene's active rendering becomes the newly generated text, verified via
     `list_renderings`/`is_active`), stops immediately after a mid-run Cancel (no scene after the
     cancelled one gets a new rendering), stops after a mid-run generation error, stops if
     `current_story_id` changes mid-run, and emits `finished` exactly once per run.
   - `test/scene/gui/test_main_window.py`: Render menu's first action is now `&Render Full
     Story...`; the three guard messages (no story / no scenes / rendering not configured); Cancel
     on the confirmation dialog is a no-op; Proceed starts a controller (monkeypatched) with the
     current story id; the action is disabled while a controller is active and re-enabled once its
     `finished` signal fires.

## Verification

- `pdm run pytest` — full suite passes, including the new/updated `gui` tests, with the
  auto-generated `htmlcov/index.html` coverage report.
- `pdm run lint` — clean (ruff, 120-char line length).
- Manual smoke check via the `run` skill: open a story with several scenes (some already rendered,
  some not), use Render > Render Full Story..., confirm the dialog's Cancel is a no-op and Proceed
  starts the run; watch the Scenes tab selection and Rendering column advance scene by scene with
  live streaming text; click Cancel partway through and confirm no further scenes are touched and
  the in-progress scene's partial text is saved/activated as usual; run it again to completion and
  confirm every scene ends up with a newly-generated active rendering and the menu action is
  re-enabled afterward.

## Log

### Review - 2026-08-30T16:06:25Z - John Hoff

Reviewed e013-render-full-story against both applicable lore items (linting, unit-testing) and spot-checked its technical claims against the current contents of rendering_column.py, entity_column/column.py, entity_column/scenes.py, and main_window.py; every claim checked -- the _on_generate_clicked/_on_generation_finished/_on_continuity_task_finished structure, _PromptPreviewDialog's button layout, the scene_selected -> current_scene_changed -> set_scene cascade, and ScenesWidget.list_widget's UserRole id storage -- matches the code exactly, so the Plan is built on an accurate premise. The Plan's Verification section explicitly requires a clean pdm run lint and a fully-passing pdm run pytest with coverage, and its test plan (step 4) correctly mirrors src/scene/gui/full_story_render.py under test/scene/gui/, satisfying both the linting and unit-testing lore with no gaps. One minor, non-blocking note: MainWindow reading self.rendering_column._llm_config directly reaches into a private attribute of another class (harmless under this repo's current ruff rule selection, which has no flake8-self/SLF rule enabled, but worth a public accessor if that ever changes); separately, the Plan's assumption that list_scenes returns position-ordered results and that sequential rendering avoids the "earlier scene unrendered" ValueError guard was flagged as outside the review's bounded surface, though it is independently confirmed correct (scene.core.scene.list_scenes orders by Scene.position). PASS-WITH-NOTES.

### Completed - 2026-08-30T16:50:05Z - John Hoff

Verification passed: pdm run pytest (569 tests, two consecutive full-suite runs) and pdm run lint both clean; full_story_render.py at 100% coverage. User performed and confirmed the manual smoke test themselves (live GUI run): Render Full Story... confirm dialog's Cancel/Proceed both work, scenes render one by one with visible live streaming, mid-run Cancel halts the whole batch, and a full run completes with every scene's active rendering refreshed.
