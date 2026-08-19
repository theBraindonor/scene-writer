---
archived: false
campaign: c004-scene-rendering-agent
created_by: John Hoff
created_on: '2026-08-19T00:52:30Z'
depends_on:
- e002-render-tui
kind: scripted
name: e003-render-regenerate-and-versions
regions:
- cli
status: completed
updated_by: John Hoff
updated_on: '2026-08-19T05:37:20Z'
---

# E003 — Render Regenerate and Versions

## Requirements
- Add a "Regenerate this scene" action to `RenderApp`, available for the currently selected scene regardless of whether it already has an active rendering: builds context via `build_render_messages` for that scene (unaffected by the target scene's own existing renderings, per the campaign's context-construction design — only scenes strictly before it matter), streams via `stream_render` into the output pane exactly like "render next scene," and on completion persists a new `Rendering` row (`create_rendering`) and activates it (`set_active_rendering`), leaving prior versions intact.
- Add a rendering-version view to the render view for the selected scene: lists all of that scene's renderings (`scene.core.rendering.list_renderings`) with an indicator of which is active, lets the writer select one to view its full text, and offers actions to activate a different one (`set_active_rendering`) or delete a version (`scene.core.rendering.delete_rendering`) — refusing, with a clear notice, to delete a scene's only rendering or its currently active rendering, requiring the writer to activate a different version first before a delete of the (then-inactive) old active version is allowed.
- Cover both additions with tests in `test/scene/cli/test_render_app.py`: a regenerate-after-existing-active-rendering scenario confirming a second `Rendering` row is created and activated while the first remains; a version-list scenario confirming activating a non-active version makes it active and updates the scene list's rendered-status display accordingly; and delete-guard scenarios (refusing to delete a scene's sole rendering, and refusing to delete the currently active rendering while another exists).

## Rationale
Completes the render TUI's scope per the campaign's version-browsing design decision — a
writer should be able to regenerate a scene and compare or select among its versions without
leaving the app or dropping to the `scene-data` CLI. Builds directly on `e002`'s
streaming/persistence wiring (regeneration reuses the same streaming-to-output-pane and
`create_rendering`/`set_active_rendering` path) and `scene.core.rendering`'s already-existing
`list_renderings`/`set_active_rendering`/`delete_rendering` functions from
`c002-initial-data-model-and-crud` — no new `scene.core`/`scene.data` work is needed, only
wiring the existing service layer into the TUI.

## Plan
1. Add the "Regenerate this scene" action to `RenderApp`, reusing `build_render_messages`/`stream_render`/`create_rendering`/`set_active_rendering` exactly as `e002`'s "render next scene" does, but targeting the currently selected scene instead of `find_next_unrendered_scene`'s result.
2. Add a version-list element to the render view showing the selected scene's renderings (via `list_renderings`) with an active indicator, a way to view any version's full text, and actions to activate (`set_active_rendering`) or delete (`delete_rendering`) a version, with the delete guard described in Requirements.
3. Extend `test/scene/cli/test_render_app.py` with the regenerate scenario, version-list/activate scenario, and delete-guard scenarios.
4. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-coordinator render`, regenerate an already-rendered scene, confirm both versions appear in the version list, activate the older one, confirm the scene list's status reflects it, and confirm deleting the sole/active version is refused with a clear message.

## Log

### Review - 2026-08-19T04:06:20Z - John Hoff

Reviewed against the two applicable lore items (linting, unit-testing), both fully honored: the Plan/Verification explicitly gate completion on zero `ruff` errors and a green `pdm run pytest` run, and the Requirements commit to new tests in the correctly mirrored `test/scene/cli/test_render_app.py` path covering the regenerate flow, version activation, and both delete-guard cases. No lore conflicts found. Flagged-but-unverified: the encounter is region-scoped to `cli` only while its Plan depends on several `scene.core.rendering` functions and `e002`'s `RenderApp`/`build_render_messages`/`stream_render` existing as described — these live outside the cited reading surface and were not chased, so their soundness (as opposed to lore compliance) is unconfirmed by this review.

### Message - 2026-08-19T04:24:39Z - John Hoff

Deviation, approved by the user during implementation: added a way to cancel an in-progress generation. Pressing Escape while "Render next scene" or "Regenerate this scene" is streaming shows a Y/N confirmation; confirming (Y) stops pulling further content from the stream, persists and activates whatever prose was received so far as a new Rendering (best-effort partial save, skipped if nothing was received yet), and shows a "Generation cancelled" notice. This was not in the originally reviewed Requirements/Plan; the user asked for it after the initial review and explicitly chose to fold it into this encounter rather than draft a separate one.

### Completed - 2026-08-19T05:37:20Z - John Hoff

Delivered: regenerate action, rendering-version browser (view/activate/delete with guards), and an escape-to-cancel flow (Y/N confirm, best-effort partial save) added mid-encounter per user request. pdm run pytest (297 passed) and pdm run lint (clean) both green; verified interactively in the real TUI, including a live LLM regenerate/cancel run.
