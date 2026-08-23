---
archived: false
campaign: c006-gui-usability
created_by: John Hoff
created_on: '2026-08-21T20:43:12Z'
depends_on: []
kind: scripted
name: e001-rendering-column-management
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-22T15:33:05Z'
---

# E001 — Rendering Column Management

## Requirements

Extend `src/scene/gui/rendering_column.py` (currently a read-only viewer of a scene's active
rendering, per `c005`'s explicit deferral) so that, for the currently selected scene, the user
can:

1. **View version history** — see every rendering generated for the scene, in generation order,
   labeled `v{index}` (1-based), matching `RenderApp`'s existing labeling scheme (there is no
   explicit version-number column on `Rendering`; order is `list_renderings()`'s `id` order).
2. **See which version is active** — the currently active rendering must be visibly marked in
   the version list, and its body is what the column's existing body view shows.
3. **Select a previous version and activate it** — choosing a different version from the list
   and confirming calls `scene.core.rendering.set_active_rendering`, and the body view updates
   to show it.
4. **Generate a new rendering** — trigger scene-drafting generation for the selected scene,
   streamed live into the UI (reasoning + content deltas, not a blocking spinner), which on
   completion creates a new `Rendering` row and makes it active. Follows the same two semantics
   `RenderApp` already has: "render next" for a scene with no active rendering yet vs.
   "regenerate" for one that already has one. Generation must respect
   `build_render_messages`'s ordering constraint (it raises `ValueError` if any scene before the
   target position lacks an active rendering) — the GUI must surface this as a clear, non-crashing
   message rather than an unhandled exception, not silently allow the action.
5. **Delete a version** — with guardrails matching `RenderApp`: the sole rendering and the
   currently active rendering may not be deleted (mirroring its
   `DELETE_SOLE_RENDERING_TEXT`/`DELETE_ACTIVE_RENDERING_TEXT` guard messages), confirmed via a
   `QMessageBox.question` dialog (matching `ScenesWidget._confirm_delete`'s existing pattern).
6. **Cancel an in-flight generation** — some GUI-appropriate affordance (e.g. a Cancel button)
   with a confirmation step, best-effort preserving partial output, mirroring `RenderApp`'s
   Escape/Y/N confirm-cancel flow's intent (not necessarily its keyboard-driven mechanism, which
   doesn't translate directly to Qt).

No changes to `scene.core`, `scene.data`, or `scene.agent` — this encounter is purely a new UI
consumer of `scene.core.rendering`'s existing functions (`create_rendering`, `list_renderings`,
`set_active_rendering`, `delete_rendering`) and `scene.agent.rendering`'s existing functions
(`find_next_unrendered_scene`, `build_render_messages`, `stream_render`).

Must be covered by `pytest-qt` tests in `test/scene/gui/test_rendering_column.py` (extending the
existing file, reusing its DB-isolation fixture pattern), and lint-clean (`ruff`, 120-character
lines). `README.md`'s GUI section must be updated to remove the "view-only" caveat and describe
the new capabilities.

## Rationale

`c005-initial-gui-application` deliberately scoped the rendering column as read-only, deferring
"generate/regenerate scene prose from the GUI" to a later campaign once the GUI's shell was in
place. That shell is now complete and stable (all seven `c005` encounters delivered), and the
developer has directed that the next campaign (`c006-gui-usability`) focus on turning the
existing GUI shell into a fully usable application — not on adding new raw story-domain
functionality. The rendering column is the most prominent read-only gap in the GUI today: every
part of the rendering workflow (create, browse, activate, delete) already exists and works,
proven out by the `RenderApp` Textual TUI (`src/scene/cli/render_app.py`, delivered in
`c004-scene-rendering-agent`) and the underlying `scene.core.rendering` service. This encounter's
job is porting that already-proven UX into the GUI's Qt widgets, not designing new behavior —
consistent with `c006`'s "mirror existing CLI/TUI behavior" design decision.

## Plan

1. Extend `RenderingColumn` (`src/scene/gui/rendering_column.py`) with a version-list
   `QListWidget` populated from `scene.core.rendering.list_renderings(session, scene_id)`,
   showing `v{index}` labels with a marker for the active one (mirroring `RenderApp`'s
   `●`/`○` + `" (active)"` convention), alongside the existing body view (updated to show the
   selected version's body, defaulting to the active one).
2. Add an "Activate" action: selecting a non-active version and confirming calls
   `set_active_rendering` inside a `with session_scope() as session:` block, then refreshes the
   list and body view — following the direct-inline-`session_scope()` convention already used by
   `EntityColumn`'s CRUD handlers (no background thread needed; this is a fast single-row
   update).
3. Add a generate/regenerate action. Determine whether the selected scene already has an active
   rendering to pick the button label/semantics (render vs. regenerate), and before allowing the
   action, check via `find_next_unrendered_scene`/position ordering whether an earlier scene in
   the story lacks an active rendering; if so, disable the action and show why, instead of
   calling `build_render_messages` and catching its `ValueError`.
4. Implement a `_RenderWorker(QObject)` + `QThread` pair mirroring `chat_panel.py`'s
   `_TurnWorker` pattern: `run()` calls `scene.agent.rendering.stream_render(config, messages)`
   (messages from `build_render_messages`) and emits a Qt signal per yielded
   `RenderReasoningDelta`/`RenderContentDelta`/`RenderComplete` event. Resolve `config` via
   `get_llm_config(AgentRole.RENDERING)`, matching `render_app.py`'s existing setup.
5. Stream `RenderContentDelta` text into the body view live as it arrives. On `RenderComplete`,
   call `create_rendering` + `set_active_rendering` in a `session_scope()` block, then refresh
   the version list and body view to reflect the new active rendering.
6. Add a "Delete" action for the selected version: block with a clear message if it's the sole or
   active rendering (matching `RenderApp`'s guard text), otherwise confirm via
   `QMessageBox.question` (matching `ScenesWidget._confirm_delete`) and call `delete_rendering`,
   then refresh.
7. Add a Cancel affordance for an in-flight generation: stopping the worker thread, confirming
   via a dialog, and best-effort saving whatever content had streamed so far as a new rendering
   (mirroring `RenderApp`'s cancel-confirm intent), or discarding it if nothing streamed yet.
8. Extend `test/scene/gui/test_rendering_column.py` (reusing its existing DB-isolation fixture,
   `monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")`) to
   cover: version list population and active marker, activate-version flow, generate flow (mock
   `stream_render` to yield synthetic events, avoiding real LLM calls), the earlier-scene-
   unrendered block, delete guardrails (sole/active blocked, otherwise succeeds), and cancel.
9. Update `README.md`'s GUI section (the paragraph noting the rendering column is "view-only for
   now") to describe the new version-browsing/activate/generate/delete capabilities.
10. Run `pdm run lint` and `pdm run pytest`; fix until both are clean.

## Verification

- `pdm run pytest` passes, including the new/updated cases in
  `test/scene/gui/test_rendering_column.py` covering: version list + active marker, activate
  flow, generate flow (streamed, via mocked `stream_render`), the earlier-scene-unrendered
  block, delete guardrails (sole/active rejected; non-active/non-sole succeeds), and cancel.
- `pdm run lint` passes with no errors.
- Manual smoke check (via the `run` skill): launch `scene-writer`, select a story/scene with
  multiple renderings, confirm the version list and active marker display correctly, activate a
  different version and confirm the body view updates, generate a new rendering and confirm it
  streams live and becomes active, attempt to delete the active/sole version (blocked with a
  clear message), delete a non-active version (succeeds), and attempt to generate for a scene
  whose earlier scenes aren't all rendered yet (blocked with a clear message).
- `README.md`'s GUI section no longer states the rendering column is view-only.

## Log

### Review - 2026-08-21T20:47:55Z - John Hoff

Reviewed e001-rendering-column-management against the two lore items applicable via world assignment (linting, unit-testing); no region-specific lore applies to `gui`. The Plan and Verification sections explicitly gate completion on `pdm run lint` passing clean and on `pdm run pytest` passing, with new/extended tests placed at `test/scene/gui/test_rendering_column.py` — the correct mirror of `src/scene/gui/rendering_column.py` — covering version listing/active-marker display, activate, generate (via mocked `stream_render`), the earlier-scene-unrendered guard, delete guardrails, and cancel. Both lore items are satisfied with no conflicts or gaps found within the reviewable surface.

### Message - 2026-08-21T23:06:18Z - John Hoff

Deviation requested by the developer during implementation, after the initial version was built and smoke-tested: refine the generate/cancel row's UI beyond the original Plan's bare button pair. Changes: (1) rename the generate button to a single unconditional "Render" label, dropping the render-vs-regenerate label toggle; (2) right-justify the generate/cancel row at a fixed button width instead of left-aligned/stretched; (3) add an unchecked-by-default "Preview Prompt" checkbox to the left of the Render button; (4) while generating, hide the Render button and checkbox entirely, showing only the right-justified, fixed-width Cancel button; (5) when "Preview Prompt" is checked, clicking Render opens a modal dialog showing the full, unabridged list of messages that `build_render_messages` will send to the LLM (to verify multi-scene continuity context is assembled correctly), with "Proceed" (starts the generation) and "Cancel" (aborts, no generation) buttons. No change to the underlying `scene.core`/`scene.data`/`scene.agent` layers or to the Requirements/Rationale/Plan's core scope (activate/delete/generate/cancel semantics) — this only reshapes the generate row's presentation and adds a pre-generation confirmation step.

### Message - 2026-08-21T23:26:39Z - John Hoff

Implemented the generate-row UI deviation described in the previous message: the button is now a single fixed-width "Render" label (no more render/regenerate toggle), the whole row (Preview Prompt checkbox + Render, or just Cancel while generating) is right-justified via a leading stretch, generate/cancel buttons are both fixed at 120px, and a new `_PromptPreviewDialog` (modal, Proceed/Cancel) shows the full `build_render_messages` output when "Preview Prompt" is checked before rendering — Cancel aborts without starting the worker, Proceed starts it exactly as before. Added 7 new tests (fixed width, hide/show during generation, dialog proceed/cancel, `_format_messages` formatting) to `test/scene/gui/test_rendering_column.py`, all passing (`pdm run pytest test/scene/gui` — 88 passed; full suite — 384 passed, after ruling out an unrelated environmental hang on this heavily-loaded dev machine that reproduced even in an untouched file, `test_chat_panel.py`, on a bad run). `pdm run lint` clean. README's GUI paragraph updated to match the new button/dialog behavior. Manually smoke-tested the new layout and checkbox in the running app.

### Message - 2026-08-22T04:22:46Z - John Hoff

Fixed a bug reported by the developer: generation wasn't reliably auto-saving on completion, and partial content wasn't guaranteed to be saved on interruption. Root cause: `_RenderWorker.run()` had no exception handling around its `stream_render` loop — any hiccup from the local LLM backend mid-stream (network drop, malformed final chunk) would silently kill the worker thread without ever emitting `finished`, so `_on_generation_finished` (the only place that saves accumulated text) never ran, leaving the column stuck showing Cancel with nothing persisted. Fixed by wrapping the loop in try/except, always emitting `finished` regardless of outcome, and adding a new `error_occurred` signal that lets `_on_generation_finished` save whatever content had accumulated (same as the existing cancel path) and show a clear "Generation error: {error}..." notice distinguishing it from a manual cancel. Verified two ways: (1) new tests `test_stream_error_after_partial_content_saves_and_notifies` and `test_stream_error_before_any_content_saves_nothing_and_notifies` in `test/scene/gui/test_rendering_column.py` (21 tests now, all passing); (2) a real end-to-end generation against the actual configured LM Studio backend (`SCENE_RENDERING_AGENT=lmstudio-roleplay`), confirming the rendering auto-saves and activates on natural completion. Full suite: 386 passed. Lint clean.

### Message - 2026-08-22T05:17:38Z - John Hoff

Two readability/usability refinements to the rendering column's body view, per the developer's direct request (they're testing live in a running instance, so verification here was lint + `pdm run pytest` only, no GUI smoke test this round): (1) increased the body view's font size by 50% (`BODY_FONT_SCALE = 1.5`, applied once at construction relative to the widget's inherited default point size) as a first pass at making generated prose easier to read; (2) the body view now auto-scrolls to the bottom as new content streams in during generation, via `QTimer.singleShot(0, ...)` scheduling the scroll for the next event-loop turn (after layout recomputes the scrollbar's range — scrolling synchronously right after `setPlainText()` uses the stale, pre-layout range and silently no-ops). Scoped to only fire from the streaming path (`_on_render_event`), so browsing a previously-saved version is unaffected. Added `test_body_view_font_is_scaled_up_from_the_default` and `test_body_view_scrolls_to_end_as_content_streams` to `test/scene/gui/test_rendering_column.py`. Full suite: 388 passed. Lint clean.

### Completed - 2026-08-22T15:33:05Z - John Hoff

Delivered full rendering-column management in the GUI: version browsing with active marker, activate/delete (with sole/active guardrails), streamed Render/Regenerate with a Preview Prompt dialog and Cancel, guaranteed save-on-completion (including on cancel or stream error), a 50% larger body font, and auto-scroll while streaming. All Verification steps confirmed: pdm run lint clean, pdm run pytest passing (391 passed on this final check), manual smoke-testing done across several rounds including a real end-to-end generation against the configured LM Studio backend, and README's GUI section updated to describe the new capabilities. The developer confirms this has reached a good stable place.
