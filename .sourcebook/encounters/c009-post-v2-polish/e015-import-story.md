---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-30T18:08:07Z'
depends_on: []
kind: scripted
name: e015-import-story
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-30T18:58:16Z'
---

## Requirements

Add **Import Story...** to the GUI's `File` menu (`src/scene/gui/main_window.py`), directly below
`Export Story...` (final order: `New Story...`, `Open Story...`, separator, `Export Story...`,
`Import Story...`, separator, `Exit`).

- On click, open a native "open file" dialog (YAML filter) to choose a previously-exported YAML
  file (the format written by `e014-export-story`'s Export Story...).
- Parse the file and create a **brand-new** story from its data (story fields, characters,
  locations, and scenes, with POV/assigned-character/assigned-location references resolved from
  the file's name-based links) — the same shape Export Story... writes, minus renderings and
  continuity snapshots (which the export never included in the first place).
- **Import never overwrites an existing story.** If a story with the same title already exists in
  the database (archived or not), the user is prompted to enter a different title before the
  import proceeds — with **"Continue"** and **"Cancel"** buttons. Continue re-checks the newly
  entered title and prompts again if it's *also* taken; Cancel aborts the entire import (nothing
  is written to the database).
- If the chosen file can't be read, isn't valid YAML, or is missing/malformed required data (no
  title/brief, a scene missing its brief, a scene referencing a character/location name that
  isn't in the file's own character/location lists, etc.), show an informational/error message
  and import nothing.
- On success, the newly created story is opened in the GUI (selected exactly as `New Story...` /
  `Open Story...` already select a story), without any further confirmation dialog.
- Cancelling the file-open dialog does nothing.

## Rationale

This is the counterpart to `e014-export-story`'s Export Story..., closing the loop so an exported
YAML file can be brought back in — for restoring a backup, transferring a story between databases,
or hand-authoring a story outside the app and loading it in. Following that encounter's precedent
(and `e011`'s before it) of keeping presentation-specific, cross-entity composition local to
`scene.gui` rather than growing `scene.core`, the import-assembly logic is added as a new
`scene.gui`-local module (`story_import.py`) alongside `story_export.py`, using existing
`scene.core` CRUD calls directly.

**Import always creates a new story rather than merging into or overwriting one** — this is an
explicit product requirement, not just an implementation convenience: an existing story's data
(and any renderings/continuity work built on it) must never be silently clobbered by an import.
Since `Story.title` has no database uniqueness constraint (confirmed in `src/scene/data/story.py`
— only `NOT NULL`/non-blank checks), title collisions have to be detected and resolved at the
application layer, which is exactly the "prompted for a new name" flow the user asked for.  The
check considers archived stories too (`list_stories(session, include_archived=True)`): an archived
story's title is still "already present in the database" in the sense that matters here — letting
an import silently create a second story with the same title as one that's merely archived (not
deleted) would be confusing.

The rename dialog's title-uniqueness check re-runs after each attempt (looping rather than a
single prompt) because a user-entered replacement title could itself already be taken — accepting
that without re-checking would violate the same "never overwrite" guarantee the first prompt exists
to protect. The dialog's button labels and order (**Cancel**, then **Continue**, Continue =
`accept()`) mirror the codebase's existing Cancel/Proceed confirmation convention
(`RenderFullStoryConfirmDialog`, `_PromptPreviewDialog`), just with wording matching what the user
asked for here (Continue rather than Proceed, since this dialog collects new input rather than
just confirming an action).

Scenes are re-numbered sequentially (`0, 1, 2, ...`) in the order they appear in the file's
`scenes` list, ignoring whatever numeric `position` values the file itself contains. The file's
list order **is** the story order (that's exactly how Export Story... wrote it — position-ordered),
so trusting list order and discarding the raw `position` field sidesteps any risk of a hand-edited
or corrupted file producing duplicate/out-of-range positions and tripping
`uq_scene_story_id_position` for no good reason.

The file is validated as a self-contained unit *before* any database write happens (bad title/
brief, a scene missing its brief, an unresolved character/location name reference, or a duplicate
character/location name all fail fast with a clear message). This matters more here than for most
of the app's other guards: unlike in-app actions, an imported file is an external input that can
be hand-edited or corrupted, so it's a real trust boundary worth validating deliberately, not
"error handling for a scenario that can't happen." That said, once validation passes, story
creation still goes through `scene.core`'s existing per-call-commit convention (no cross-entity
transaction wrapping the whole import, matching every other multi-entity operation in this
codebase, e.g. `FullStoryRenderController`'s scene-by-scene commits) — a database-level failure
partway through (e.g. a duplicate character name the file-level validation didn't catch) can still
leave a partially-created story behind, surfaced to the user as an error rather than silently
rolled back.

The story's `is_archived` flag is preserved from the export data via a follow-up
`archive_story(session, story_id)` call after creation, rather than adding an `is_archived`
parameter to `scene.core.story.create_story` — a one-off follow-up call for this one caller is a
smaller footprint than growing that function's signature for a rarely-set flag.

## Plan

1. Add `src/scene/gui/story_import.py`:
   - `parse_story_import_file(path: str) -> dict` — open and `yaml.safe_load` the file; wrap
     `OSError` and `yaml.YAMLError` in `ValueError` with a user-facing message. Validate: the
     parsed value is a `dict`; `data["story"]` is a `dict` with non-blank `title` and
     `story_brief`; `data.get("characters", [])`, `data.get("locations", [])`,
     `data.get("scenes", [])` are lists. While collecting `character_names`/`location_names` sets
     from the characters/locations lists, raise `ValueError` for any character/location entry
     that isn't a dict, is missing a non-blank `name`, or repeats a name already seen. For each
     scene entry, raise `ValueError` if it isn't a dict or is missing a non-blank `brief`, or if
     its `pov_character` (when set) or any name in its `characters`/`locations` lists isn't in
     `character_names`/`location_names`. Return the parsed `dict` unchanged on success (callers
     read directly from it — no separate normalized structure).
   - `story_title_exists(session: Session, title: str) -> bool` — `any(story.title == title for
     story in list_stories(session, include_archived=True))`.
   - `import_story(session: Session, data: dict, title: str) -> int` — create the story via
     `scene.core.story.create_story(session, title=title, story_brief=data["story"]["story_brief"],
     style_guidance=data["story"].get("style_guidance"),
     generation_guideance=data["story"].get("generation_guideance"))`. For each entry in
     `data.get("characters", [])`, `scene.core.character.create_character(...)`, keyed by name in
     a local `characters_by_name` dict. For each entry in `data.get("locations", [])`,
     `scene.core.location.create_location(...)`, keyed by name in `locations_by_name`. For each
     `(position, scene)` in `enumerate(data.get("scenes", []))` (position = list index, not the
     file's own `position` field), `scene.core.scene.create_scene(session, story_id=story.id,
     position=position, brief=scene["brief"], heading=scene.get("heading"),
     required_actions=scene.get("required_actions"), target_length=scene.get("target_length"),
     desired_outcome=scene.get("desired_outcome"), pov_character_id=characters_by_name[pov].id if
     (pov := scene.get("pov_character")) else None)`, then
     `scene.core.scene_character.assign_character` / `scene.core.scene_location.assign_location`
     for each name in the scene's `characters`/`locations` lists. If `data["story"].get(
     "is_archived")` is true, call `scene.core.story.archive_story(session, story.id)` at the end.
     Return the new story's id.

2. Update `src/scene/gui/main_window.py`:
   - Import `QFileDialog` from `PySide6.QtWidgets`; `IntegrityError` from `sqlalchemy.exc`;
     `parse_story_import_file`, `story_title_exists`, `import_story`, `DuplicateStoryTitleDialog`
     from the new `scene.gui.story_import`.
   - In `_build_menu_bar`, add `import_action = file_menu.addAction("&Import Story...")` wired to
     a new `_on_import_story` handler, placed right after `export_action` and before the existing
     `file_menu.addSeparator()` (so it lands directly below Export Story..., inside the same
     separator-bounded group).
   - `_on_import_story(self) -> None`: `path, _ = QFileDialog.getOpenFileName(self, "Import
     Story", "", "YAML Files (*.yaml *.yml);;All Files (*)")`; return if cancelled (`not path`).
     `try: data = parse_story_import_file(path) except ValueError as error:
     QMessageBox.critical(self, "Import Story", str(error)); return`. Call
     `title = self._resolve_import_title(data["story"]["title"])`; return if `None`. Under
     `session_scope()`, `try: story_id = import_story(session, data, title) except (ValueError,
     IntegrityError) as error: QMessageBox.critical(self, "Import Story", f"Could not import the
     story: {error}"); return`. Finally, `self._on_story_selected(story_id)` (same cascade
     `New Story...`/`Open Story...` already drive).
   - `_resolve_import_title(self, title: str) -> str | None`: loop — under `session_scope()`,
     check `story_title_exists(session, title)`; if not taken, return `title`. If taken, show
     `DuplicateStoryTitleDialog(title, self)`; if not accepted, return `None`; otherwise set
     `title = dialog.new_title()` and loop again.

3. In `src/scene/gui/story_import.py`, add `DuplicateStoryTitleDialog(QDialog)`: modal, title
   "Import Story", a word-wrapped `QLabel` reading
   `f'A story named "{title}" already exists. Enter a different title to continue the import.'`,
   a `QLineEdit` pre-filled with `title`, and a bottom button row **Cancel** (`reject()`) then
   **Continue** (`accept()`) — mirroring `RenderFullStoryConfirmDialog`'s Cancel/Proceed order and
   semantics. The Continue button is disabled whenever the line edit's stripped text is empty
   (connected to `textChanged`, re-evaluated on init). `new_title(self) -> str` returns the line
   edit's stripped text.

4. Tests:
   - New `test/scene/gui/test_story_import.py`: `parse_story_import_file` successfully parses a
     well-formed file (built via `build_story_export_data` + `yaml.safe_dump` to a `tmp_path`
     file, keeping the two modules' shapes verifiably in sync); raises `ValueError` for a missing
     file, invalid YAML content, a non-mapping top-level document, a missing/blank
     title/story_brief, a scene missing its brief, a scene referencing an unknown POV character,
     an unknown assigned character, or an unknown assigned location, a character/location missing
     its name, and a duplicate character/location name. `story_title_exists` returns `True` for
     both an active and an archived existing story's exact title and `False` otherwise.
     `import_story` creates the story with the given `title` (not the file's own, when they
     differ) and correct `story_brief`/`style_guidance`/`generation_guideance`; creates all
     characters/locations; creates scenes in file-list order with sequential `0..N-1` positions
     regardless of the file's own `position` values, with correct `pov_character_id` and
     character/location assignments resolved by name; archives the created story when the file's
     `is_archived` is true and leaves it unarchived when false/absent; and a full round-trip test
     (`build_story_export_data` on a fully-populated seeded story → `yaml.safe_dump`/`safe_load` →
     `parse_story_import_file`-style validated dict → `import_story` into a fresh story →
     `build_story_export_data` on the new story) matches the original data except for `title`.
   - Update `test/scene/gui/test_main_window.py`: File-menu ordered-actions test updated to
     `["&New Story...", "&Open Story...", "&Export Story...", "&Import Story...", "E&xit"]`;
     `test_import_story_with_cancelled_file_dialog_does_nothing` (monkeypatch
     `QFileDialog.getOpenFileName` to return `("", "")`; assert no `current_story_changed` signal
     and no new story in the database); `test_import_story_with_invalid_file_shows_error`
     (monkeypatch `getOpenFileName` to a path whose content isn't valid YAML/is missing required
     data; assert `QMessageBox.critical` shown and no new story created);
     `test_import_story_without_title_conflict_imports_and_selects_the_story` (monkeypatch
     `getOpenFileName` to a valid exported-story file with a title not already in the database;
     assert, via `qtbot.waitSignal(window.current_story_changed)`, that a new story matching the
     file's data now exists and is selected); `test_import_story_with_title_conflict_prompts_and_
     imports_under_new_title` (seed an existing story sharing the file's title; monkeypatch
     `DuplicateStoryTitleDialog` with a fake that returns an accepted result and a new title;
     assert the import proceeds under the new title, leaving the original story untouched, and
     the new story is selected); `test_import_story_title_conflict_cancelled_aborts_import`
     (same setup, fake dialog rejected; assert no new story is created and no selection change
     occurs).

## Verification

- `pdm run pytest` — full suite passes, including the new/updated `gui` tests, with the
  auto-generated `htmlcov/index.html` coverage report.
- `pdm run lint` — clean (ruff, 120-char line length).
- Manual smoke check via the `run` skill: export a story with characters, locations, and several
  scenes (including one with a POV character and assigned characters/locations) via Export
  Story..., then use Import Story... on that file — confirm it opens the new story (identical
  content, new database id) in the GUI. Re-run Import Story... on the same file again and confirm
  the "already exists" prompt appears; enter a new title and Continue, confirming a second story
  is created and opened under that title without touching the first. Try again and Cancel the
  prompt, confirming nothing is created. Finally, point Import Story... at a deliberately broken
  YAML file and confirm a clear error message appears with nothing imported.

## Log

### Review - 2026-08-30T18:14:30Z - John Hoff

e015-import-story's Plan satisfies both applicable lore items — linting (Verification runs `pdm run lint`) and unit-testing (new `test/scene/gui/test_story_import.py` correctly mirrors the new `story_import.py` module, `test_main_window.py` is updated, and Verification runs `pdm run pytest` with coverage) — and its data-shape assumptions are verified consistent with e014's actual `build_story_export_data` output (field names, nesting, and the position/enumerate rationale all line up). Two implementation details fall outside the bounded review surface and were flagged but not chased: the exact `scene.core` CRUD signatures the Plan's abbreviated calls rely on, and the current literal structure of `main_window.py` the Plan proposes to extend. PASS-WITH-NOTES.

### Completed - 2026-08-30T18:58:16Z - John Hoff

Verification passed: pdm run pytest (616 tests, including new test/scene/gui/test_story_import.py and updated test/scene/gui/test_main_window.py) and pdm run lint both clean; story_import.py at 100% coverage. Manual smoke test via a driver script (real MainWindow, real menu trigger, real DB) confirmed: a no-conflict import opens an identical new story; a title conflict shows the real DuplicateStoryTitleDialog and imports under the entered new title on Continue; Cancel on that dialog aborts cleanly with nothing created; a broken YAML file shows a clear error and imports nothing.
