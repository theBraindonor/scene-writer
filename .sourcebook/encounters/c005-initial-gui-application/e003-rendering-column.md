---
archived: false
campaign: c005-initial-gui-application
created_by: John Hoff
created_on: '2026-08-20T22:47:02Z'
depends_on:
- e002-entity-column-crud
kind: scripted
name: e003-rendering-column
regions:
- gui
status: draft
updated_by: John Hoff
updated_on: '2026-08-20T22:47:05Z'
---

# E003 — Rendering Column

## Requirements
- Replace the rendering-column placeholder from `e001` with a widget that reacts to `e002`'s
  `current_scene_changed` signal (and to `current_story_changed`, since switching stories resets
  the selected scene to `None`): when no scene is selected, show an empty-state message; when a
  scene is selected, look up its active rendering via `scene.core.rendering.list_renderings`
  (the entry with `is_active` true, if any) and display its body, read-only.
- When the selected scene has no active rendering yet, show a distinct empty-state message
  (mirroring `RenderApp`'s `NO_RENDERINGS_TEXT` precedent) rather than a blank pane, so a writer
  can tell "no rendering yet" apart from "nothing selected."
- No editing, no generation/regeneration, no version browsing or streaming in this encounter —
  the campaign scopes this column as view-only; those remain the TUI's job (`scene-coordinator
  render`) for now.
- Cover with tests in `test/scene/gui/test_rendering_column.py` using `pytest-qt`: selecting a
  scene with an active rendering displays its body; selecting a scene with no rendering shows
  the empty-state message; selecting no scene (or switching to a story with no scene selected)
  shows the no-selection message; switching the active rendering for a scene (e.g. via
  `scene.core.rendering.set_active_rendering`) and re-selecting it shows the newly active body.

## Rationale
Completes the "view" side of the campaign's four-region layout with the simplest possible
implementation the campaign's scope allows: a read-only lookup against `scene.core.rendering`,
deliberately excluding generation/streaming/version-browsing per the campaign's explicit
out-of-scope note (that stays on `scene-coordinator render` until a later campaign brings
rendering workflows into the GUI). Depends on `e002` for the `current_scene_changed` signal and
the `QSplitter` region this widget fills.

## Plan
1. Create `src/scene/gui/rendering_column.py` with a widget that connects to
   `current_scene_changed` (and `current_story_changed`, to reset on story switch) and renders
   the selected scene's active rendering body, or one of the two empty-state messages.
2. Wire `MainWindow` (from `e001`) to replace its rendering-column placeholder with this widget
   and connect it to `e002`'s entity-column signals.
3. Add `test/scene/gui/test_rendering_column.py` covering the scenarios in Requirements, using
   the `isolated_database` monkeypatch pattern and `pytest-qt`'s `qtbot`.
4. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-writer`: select a scene with an existing active rendering (created
  via `scene-coordinator render` or `scene-data`) and confirm its text displays; select a scene
  with no rendering and confirm the empty-state message appears; switch stories and confirm the
  column resets.

## Log
