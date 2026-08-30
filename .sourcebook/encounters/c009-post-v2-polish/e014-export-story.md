---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-30T17:05:39Z'
depends_on: []
kind: scripted
name: e014-export-story
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-30T18:02:26Z'
---

## Requirements

Add **Export Story...** to the GUI's `File` menu (`src/scene/gui/main_window.py`), directly below
`Open Story...` with a separator between the two (the existing separator currently sitting
between `Open Story...` and `Exit` moves to sit between the new `Export Story...` action and
`Exit`, so the final order is: `New Story...`, `Open Story...`, separator, `Export Story...`,
separator, `Exit`).

- On click, if no story is currently selected (`self.current_story_id is None`), show an
  informational message ("Select a story first.") and do nothing else — matching the existing
  guard convention used by every Render menu action.
- Otherwise, open a native save-file dialog (YAML filter) and write the active story's full data
  to the chosen path as YAML: the story's own fields, all of its characters, all of its
  locations, and all of its scenes (each scene's assigned characters/locations and POV character,
  referenced by name rather than internal database id).
- **Renderings and continuity snapshots are deliberately excluded** — the export contains only
  the story's structural/narrative-planning data, none of the generated prose or continuity
  state.
- Cancelling the save dialog does nothing further (no file written, no error).

## Rationale

This gives the developer a portable, human-readable snapshot of a story's construction-phase data
(everything entered by hand or via the coordinating agent) independent of the SQLite database —
useful for backup, review outside the app, or as a starting point for building a story elsewhere.
YAML is chosen (over e.g. JSON) because it's the more readable/reviewable format for prose-heavy
free-text fields like `story_brief` and scene `brief`s, and matches the project's existing use of
YAML for other human-authored/reviewed data (`agent-prompts.yaml`, `models.example.yaml`).

Renderings and continuity snapshots are excluded per explicit instruction — they're generated
*output* of the pipeline, not the input/planning data the export is meant to capture, and
including them would make the export a much larger, less reviewable, semi-redundant copy of the
database rather than a focused planning-data snapshot.

Following e011's precedent (`combine_story_prose` composing across entities directly via existing
`scene.core` CRUD calls rather than growing `scene.core` a cross-entity aggregation module for one
presentation-specific concern), the export-assembly function is added as a new `scene.gui`-local
module rather than to `scene.core.story`.

Scenes reference their POV character and assigned characters/locations **by name** rather than by
database id: ids are meaningless outside this database (and thus useless to a reader of the
exported file), while names are already guaranteed unique per story
(`uq_character_story_id_name`, `uq_location_story_id_name`), so name-based references are
unambiguous and far more readable. The export nests story fields under a top-level `story:` key
(rather than flattening them alongside `characters`/`locations`/`scenes`) purely for readability —
it groups the story's own attributes together and keeps the export's shape self-explanatory
without needing a schema doc.

`PyYAML` is already present in `pdm.lock` as a transitive dependency (pulled in by another
package), but is not declared directly in `pyproject.toml` and nothing under `src/` currently
imports it. Since this encounter adds a direct `import yaml`, it must be promoted to an explicit
dependency — relying on an undeclared transitive package would silently break if the package
pulling it in ever drops it.

The existing `NO_STORY_SELECTED_FOR_RENDER_TEXT` constant (text: "Select a story first.") is
renamed to `NO_STORY_SELECTED_TEXT`, since it will now also guard a File menu action that has
nothing to do with rendering — keeping the old name would be actively misleading at its new call
site, and this is a same-file, same-change rename rather than an unrelated cleanup.

## Plan

1. `pdm add pyyaml` to promote PyYAML from a transitive lock entry to a direct dependency in
   `pyproject.toml` (and update `pdm.lock` accordingly).

2. Add `src/scene/gui/story_export.py`:
   - `build_story_export_data(session: Session, story_id: int) -> dict` — call
     `scene.core.story.get_story`; raise `ValueError(f"Story {story_id} not found")` if `None`.
     Build `characters_by_id = {c.id: c for c in scene.core.character.list_characters(session,
     story_id)}` (already position/id-ordered). For each `scene.core.scene.list_scenes(session,
     story_id)` entry (position-ordered), build a dict with `position`, `heading`, `brief`,
     `required_actions`, `desired_outcome`, `target_length`, `pov_character` (the name of
     `characters_by_id.get(scene.pov_character_id)` if set, else `None`), `characters` (names from
     `scene.core.scene_character.list_characters_for_scene`), and `locations` (names from
     `scene.core.scene_location.list_locations_for_scene`). Return:
     ```python
     {
         "story": {
             "title": story.title,
             "story_brief": story.story_brief,
             "style_guidance": story.style_guidance,
             "generation_guideance": story.generation_guideance,
             "is_archived": bool(story.is_archived),
         },
         "characters": [
             {"name": c.name, "description": c.description, "motive": c.motive}
             for c in characters_by_id.values()
         ],
         "locations": [
             {"name": location.name, "description": location.description}
             for location in list_locations(session, story_id)
         ],
         "scenes": scenes,
     }
     ```
   - `save_yaml_to_file(parent: QWidget, data: dict) -> bool` — mirrors
     `full_story_dialog.save_text_to_file`: `QFileDialog.getSaveFileName(parent, "Export Story",
     "", "YAML Files (*.yaml *.yml);;All Files (*)")`; return `False` if cancelled; append
     `.yaml` if the chosen path has no extension; write with
     `yaml.safe_dump(data, file, sort_keys=False, allow_unicode=True)` under `open(path, "w",
     encoding="utf-8")`; on `OSError`, show `QMessageBox.critical(parent, "Export Story", f"Could
     not export the story: {error}")` and return `False`; return `True` on success.

3. Update `src/scene/gui/main_window.py`:
   - Rename `NO_STORY_SELECTED_FOR_RENDER_TEXT` to `NO_STORY_SELECTED_TEXT` (update its three
     existing use sites: `_on_render_full_story`, `_on_view_full_story`, `_on_save_full_story`).
   - Import `build_story_export_data`, `save_yaml_to_file` from `scene.gui.story_export`.
   - In `_build_menu_bar`, after `open_action` and before the existing `file_menu.addSeparator()`,
     insert a new `file_menu.addSeparator()` followed by `export_action =
     file_menu.addAction("&Export Story...")` wired to a new `_on_export_story` handler. (The
     existing separator, unchanged in code, now reads as sitting between `Export Story...` and
     `Exit` once the new one is inserted before it.)
   - `_on_export_story(self) -> None`: guard on `self.current_story_id is None` ->
     `QMessageBox.information(self, "Export Story", NO_STORY_SELECTED_TEXT)` and return;
     otherwise build `data = build_story_export_data(session, self.current_story_id)` under
     `session_scope()` and call `save_yaml_to_file(self, data)`.

4. Tests:
   - New `test/scene/gui/test_story_export.py`: `build_story_export_data` returns the story's own
     fields under `story`, all characters/locations, and scenes in position order with correct
     `pov_character`/`characters`/`locations` name references (including a scene with no POV
     character and no assigned characters/locations); raises `ValueError` for a nonexistent
     `story_id`; the returned dict has no key or nested data derived from renderings or continuity
     snapshots even when the seeded story has both. `save_yaml_to_file`: writes valid YAML
     (round-tripped via `yaml.safe_load`) matching the given data to the chosen path (monkeypatch
     `QFileDialog.getSaveFileName`); returns `False` without writing when cancelled; appends
     `.yaml` when the chosen name has no suffix; shows `QMessageBox.critical` and returns `False`
     on a write failure.
   - Update `test/scene/gui/test_main_window.py`: add a File-menu ordered-actions test (mirroring
     `test_render_menu_has_render_view_and_save_full_story_actions`, filtering out separator
     actions via `action.isSeparator()`) asserting `["&New Story...", "&Open Story...", "&Export
     Story...", "E&xit"]`; add `test_export_story_with_no_story_selected_shows_message` (mirrors
     `test_save_full_story_with_no_story_selected_shows_message`, title `"Export Story"`); add
     `test_export_story_saves_export_data` seeding a story with a scene/character/location,
     monkeypatching `main_window_module.save_yaml_to_file` to capture its call, triggering
     `&Export Story...`, and asserting it was called once with the same dict
     `build_story_export_data` would produce for that story.

## Verification

- `pdm run pytest` — full suite passes, including the new/updated `gui` tests, with the
  auto-generated `htmlcov/index.html` coverage report.
- `pdm run lint` — clean (ruff, 120-char line length).
- Manual smoke check via the `run` skill: open a story with characters, locations, and a few
  scenes (some with a POV character and assigned characters/locations, at least one rendered with
  a continuity snapshot present), use File > Export Story..., save to a temp path, and confirm the
  resulting YAML contains the story/characters/locations/scenes data with correct name references
  and no renderings or continuity-snapshot content; separately confirm File > Export Story... with
  no story selected shows the "Select a story first." message and writes nothing, and that
  cancelling the save dialog leaves no file behind.

## Log

### Review - 2026-08-30T17:19:21Z - John Hoff

PASS-WITH-NOTES: e014-export-story's Plan is well-specified and consistent with both applicable lore items — Verification runs `pdm run lint` (satisfying the linting standard) and `pdm run pytest` with new tests at `test/scene/gui/test_story_export.py` and additions to `test/scene/gui/test_main_window.py` that mirror the module structure of the new `src/scene/gui/story_export.py` and the existing `main_window.py` handlers (satisfying the unit-testing standard's mirrored-path and pass-before-completion requirements). Independent checks against `src/scene/gui/main_window.py`, `src/scene/gui/full_story_dialog.py`, `pyproject.toml`, and `pdm.lock` confirm every factual claim in the Plan and Rationale (existing constant/handler structure, the `save_text_to_file` pattern being mirrored, and PyYAML's current transitive-only dependency status) — no conflicts with lore or contradictions with the actual codebase state were found.

### Completed - 2026-08-30T18:02:26Z - John Hoff

Verification passed: pdm run pytest (581 tests, including new test/scene/gui/test_story_export.py and updated test/scene/gui/test_main_window.py) and pdm run lint both clean; story_export.py at 100% coverage. Manual smoke test via a driver script (real MainWindow, real menu trigger, real DB) confirmed: no-story-selected shows "Select a story first." and writes nothing; cancelling the save dialog writes nothing; a real export produces valid YAML with correct story/characters/locations/scenes data and name-based references, with no rendering body or continuity-snapshot content present. pdm install -G dev synced cleanly with PyYAML now a direct dependency.
