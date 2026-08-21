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
status: completed
updated_by: John Hoff
updated_on: '2026-08-21T02:31:57Z'
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

### Review - 2026-08-21T01:47:10Z - John Hoff

e002-entity-column-crud honors both applicable lore items: the Plan explicitly gates completion on `pdm run lint` (ruff, 120-char lines) and `pdm run pytest` passing, and its designated test file `test/scene/gui/test_entity_column.py` correctly mirrors the planned `src/scene/gui/entity_column.py` implementation module per the unit-testing convention, with a concrete, non-trivial set of test scenarios specified in Requirements. One minor latent ambiguity: Plan step 1's escape hatch to split the widget into a package if it grows large enough isn't paired with a corresponding contingency for the test mirroring structure, which would need updating to stay conformant if that path is taken. Reliance on e001's isolated-database/qtbot test patterns is reasonable continuity and outside this encounter's cited surface. No lore conflicts found; approved to proceed.

### Message - 2026-08-21T02:31:52Z - John Hoff

Automated verification: `pdm run pytest` (337 passed, incl. 41 tests in test/scene/gui/) and `pdm run lint` (zero errors) both pass. Manual verification of `pdm run scene-writer` was done by the developer directly (not automated), who found and reported two UX defects, both fixed and covered by new tests: (1) none of the sections (Story/Scenes/Characters/Locations/Stories) had a visible heading, so list contents and forms were unidentifiable without knowing the schema — added a shared `section_heading` helper (`scene/gui/section_heading.py`) and applied it to every section; (2) the character/location assignment checklists in the Scenes section used QListWidget's default expanding size policy, leaving blank space below short lists that looked like a selectable empty row — added `scene/gui/list_sizing.py`'s `fit_list_height_to_contents` and applied it to every entity list embedded in the crowded entity-column layout (scenes, characters, locations, and the two assignment checklists), while deliberately leaving the sidebar's story list unconstrained since it's the sole content of its own full-height pane, not a stacked/crowded context.

### Completed - 2026-08-21T02:31:57Z - John Hoff

All tests pass (337/337) and lint is clean. Developer performed manual verification directly and reported two UX issues (missing section headings, phantom empty rows in short assignment lists), both fixed and covered by new tests per the message above.
