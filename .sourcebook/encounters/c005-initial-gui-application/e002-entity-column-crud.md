---
archived: false
campaign: c005-initial-gui-application
created_by: John Hoff
created_on: '2026-08-20T22:46:47Z'
depends_on:
- e001-gui-app-skeleton-and-sidebar
kind: scripted
name: e002-entity-column-crud
regions:
- gui
status: draft
updated_by: John Hoff
updated_on: '2026-08-20T22:46:50Z'
---

# E002 — Entity Column CRUD

## Requirements
- Replace the entity-column placeholder from `e001` with a widget that reacts to
  `MainWindow.current_story_changed`: when no story is selected, it shows an empty-state
  message; when a story is selected, it shows that story's full structural data, organized into
  a story-detail section plus three entity sections (Scenes, Characters, Locations).
- **Story detail**: view/edit the selected story's `title`, `scenario`, and `style_guidance` via
  `scene.core.story.update_story`, and archive/unarchive it via `scene.core.story.archive_story`
  / `unarchive_story` — completing the story-entity CRUD surface the sidebar's create action
  (from `e001`) started.
- **Scenes**: list the story's scenes (`scene.core.scene.list_scenes`) in position order; create
  (`create_scene`), edit (`heading`, `description`, `required_actions`, `length`, `position` via
  `update_scene`), and delete (`delete_scene`, behind a confirmation dialog) a scene; for the
  selected scene, manage which characters and locations are assigned to it via
  `scene.core.scene_character`/`scene.core.scene_location`'s assign/unassign functions.
- **Characters**: list, create, edit (`name`, `description`, `motive`), and delete (behind a
  confirmation dialog) via `scene.core.character`.
- **Locations**: list, create, edit (`name`, `description`), and delete (behind a confirmation
  dialog) via `scene.core.location`.
- Track the selected scene as `current_scene_id` and emit a Qt signal (e.g.
  `current_scene_changed(int | None)`) whenever it changes — the interface contract `e003`'s
  rendering column connects to, mirroring `e001`'s `current_story_changed` pattern. Selecting a
  different story (or none) resets `current_scene_id` to `None` and emits the signal.
- Cover the above with tests in `test/scene/gui/test_entity_column.py` using `pytest-qt`:
  creating/editing/deleting a scene, character, and location each updates both the database and
  the displayed list; assigning/unassigning a character or location to a scene updates the
  assignment tables; editing story fields and archiving/unarchiving persist; selecting a scene
  emits `current_scene_changed` with its id.

## Rationale
This is the direct-edit half of the campaign's "one code path, one source of truth" design
decision: every action here calls the same `scene.core` functions the coordinating agent's
tools already call, so once `e004` wires chat in, both ways of changing data behave identically
with no divergent logic to keep in sync. Story-level editing (title/scenario/style guidance,
archive/unarchive) lands here rather than in the sidebar because it's the same "view and edit
the entities" surface as scenes/characters/locations, just for the story itself, and keeps all
entity CRUD in one place. Depends on `e001` for the window shell, the `QSplitter` region this
widget fills, and the `current_story_changed` signal it consumes.

## Plan
1. Create `src/scene/gui/entity_column.py` (or a package, if the three entity sections and the
   story-detail section grow large enough to warrant splitting into separate modules) with the
   top-level widget that listens for `current_story_changed` and re-renders.
2. Implement the story-detail section (view/edit fields, archive/unarchive) against
   `scene.core.story`.
3. Implement the Scenes section: list, create/edit/delete forms, and character/location
   assignment management for the selected scene, against `scene.core.scene` and
   `scene.core.scene_character`/`scene.core.scene_location`. Emit `current_scene_changed` when
   the selected scene changes.
4. Implement the Characters section against `scene.core.character`.
5. Implement the Locations section against `scene.core.location`.
6. Wire delete actions behind a `QMessageBox` confirmation before calling the underlying
   `delete_*` function.
7. Wire `MainWindow` (from `e001`) to replace its entity-column placeholder with this widget and
   connect it to `current_story_changed`.
8. Add `test/scene/gui/test_entity_column.py` covering the scenarios in Requirements, using the
   `isolated_database` monkeypatch pattern and `pytest-qt`'s `qtbot`.
9. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-writer`: select a story, edit its scenario/style guidance, archive
  and unarchive it; create/edit/delete a scene, a character, and a location; assign a character
  and a location to a scene and confirm the assignment persists (e.g. reopening the story or
  checking via `scene-data`).

## Log
