---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-30T14:35:34Z'
depends_on: []
kind: scripted
name: e011-full-story-view-and-save
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-30T15:08:42Z'
---

## Requirements

Replace the two placeholder actions under the GUI's `Render` menu (`src/scene/gui/main_window.py`,
added inert in e010-gui-menu-bar) with real functionality:

- **View Full Story...** — combine every scene's currently-active rendering body into a single
  block of text, in scene position order, and display it in a large, resizable modal dialog. The
  dialog's text uses the same scaled font as the Rendering column's prose view
  (`RenderingColumn.BODY_FONT_SCALE`). The text is read-only. At the bottom of the dialog are two
  buttons: **Save...** and **Close**.
- **Save...** (on the new dialog) — opens a native save-file dialog so the developer can save the
  combined text to disk under a name of their choosing, as a plain-text file.
- **Save Full Story...** — rename of the current **Export Full Story...** menu action. Combines
  the story's prose exactly as above and invokes the *same* save-to-file flow directly, without
  opening the viewer dialog first.

If no story is currently selected, both menu actions show an informational message instead of
doing anything else.

## Rationale

This is the first real functionality behind the `Render` menu's two placeholder actions from
e010-gui-menu-bar (`QMessageBox.information(..., "Not yet implemented.")`). The user wants a way
to read a story's prose as one continuous piece (for a read-through pass) and to get that same
text onto disk, either straight from the menu or after having reviewed it in the viewer first —
hence both entry points ending at one shared save routine rather than two separate
implementations that could drift apart. Renaming "Export" to "Save" better matches what the
action actually does (a file save, not a format conversion/export).

Matching the Rendering column's `BODY_FONT_SCALE`-scaled font keeps the full-story read-through
visually consistent with the per-scene prose view it's assembled from, rather than introducing a
second, differently-sized reading experience for the same content.

The combining logic is a new helper local to `scene.gui` (not added to `scene.core`), following
`RenderingColumn`'s own precedent (`_earlier_scenes_rendered`) of composing across entities using
existing `scene.core` CRUD calls (`list_scenes`, `list_renderings`) directly against a
caller-supplied session, rather than growing `scene.core` a cross-entity module for one
presentation-specific concatenation.

## Plan

1. Add `src/scene/gui/full_story_dialog.py`:
   - `combine_story_prose(session, story_id) -> str` — iterate `list_scenes(session, story_id)`
     (already position-ordered); for each scene, find its active rendering via
     `list_renderings(session, scene.id)` (`rendering.is_active`); join the active renderings'
     `body` text with a blank-line separator. Scenes with no active rendering are skipped rather
     than erroring.
   - `save_text_to_file(parent: QWidget, text: str) -> bool` — `QFileDialog.getSaveFileName`
     (title "Save Full Story", filter `"Text Files (*.txt);;All Files (*)"`). Returns `False`
     without touching the filesystem if the dialog is cancelled (empty path). Appends `.txt` when
     the chosen name has no extension. Writes `text` to the path as UTF-8; on `OSError`, shows
     `QMessageBox.critical` with the error and returns `False`; returns `True` on success.
   - `FullStoryDialog(QDialog)` — takes the combined `text` and an optional parent. Modal, sized
     generously (e.g. 900x700) so it reads as a dedicated viewer rather than a small popup. A
     read-only `QPlainTextEdit` showing `text`, its font set to the view's own default font with
     point size scaled by `RenderingColumn.BODY_FONT_SCALE` (mirroring `RenderingColumn.body_view`'s
     own font setup). Bottom row: **Save...** button calling `save_text_to_file(self, text)`, and
     **Close** button calling `self.accept()`.

2. Update `src/scene/gui/main_window.py`:
   - Import `FullStoryDialog`, `combine_story_prose`, `save_text_to_file` from
     `scene.gui.full_story_dialog`, and `session_scope` from `scene.data.database`.
   - In `_build_menu_bar`, change the second Render action's label from `&Export Full Story...` to
     `&Save Full Story...` and connect it to a renamed `_on_save_full_story` handler.
   - `_on_view_full_story`: if `self.current_story_id is None`, show
     `QMessageBox.information(self, "View Full Story", "Select a story first.")` and return;
     otherwise build the combined text under `session_scope()` via `combine_story_prose` and open
     `FullStoryDialog(text, self).exec()`.
   - `_on_save_full_story` (renamed from `_on_export_full_story`): same no-story guard (title
     "Save Full Story"); otherwise build the combined text the same way and call
     `save_text_to_file(self, text)`.

3. Tests:
   - New `test/scene/gui/test_full_story_dialog.py` covering: `combine_story_prose` joins active
     renderings in position order and skips a scene with no active rendering (and returns `""` for
     a story with none at all); `save_text_to_file` writes the given text to the chosen path
     (monkeypatching `QFileDialog.getSaveFileName`), returns `False` without writing when the
     dialog is cancelled, appends `.txt` when the chosen name has no suffix, and shows
     `QMessageBox.critical` and returns `False` on a write failure; `FullStoryDialog` sets the
     given text on its view, scales its font by `BODY_FONT_SCALE` off the view's own default point
     size, and its Save/Close buttons call `save_text_to_file` / accept the dialog respectively.
   - Update `test/scene/gui/test_main_window.py`: replace
     `test_render_menu_actions_show_placeholder_messages` with tests asserting the Render menu's
     second action now reads `&Save Full Story...`; that both actions show an informational
     "Select a story first." message when no story is selected; that View Full Story opens a
     `FullStoryDialog` (monkeypatched) seeded with the combined prose of a story's rendered scenes;
     and that Save Full Story calls `save_text_to_file` (monkeypatched) with that same combined
     text, without opening the viewer dialog.

## Verification

- `pdm run pytest` — full suite passes, including the new/updated `gui` tests, with the
  auto-generated `htmlcov/index.html` coverage report.
- `pdm run lint` — clean (ruff, 120-char line length).
- Manual smoke check via the `run` skill: open a story with at least two rendered scenes, use
  Render > View Full Story... to confirm the combined text, font size, and Save.../Close buttons
  all look right, then Save... to a temp file and confirm its contents; separately use Render >
  Save Full Story... directly and confirm it saves the same combined text without opening the
  viewer.

## Log

### Review - 2026-08-30T14:41:24Z - John Hoff

Reviewed against the two lore items applicable to the gui region (linting, unit-testing): both are explicitly satisfied by the encounter's Verification section (pdm run lint and pdm run pytest, with tests added/updated under test/scene/gui/ correctly mirroring the new/changed src/scene/gui/ modules). Spot-checked the Plan's technical claims against the actual current state of src/scene/gui/main_window.py and src/scene/gui/rendering_column.py: the described placeholder actions, BODY_FONT_SCALE usage, and the _earlier_scenes_rendered-style precedent for composing across entities locally in scene.gui all check out. No lore conflicts or gaps found; no unverifiable concerns to flag.

### Message - 2026-08-30T15:07:19Z - John Hoff

Deviation from the reviewed Plan: at the user's request during implementation, combine_story_prose (src/scene/gui/full_story_dialog.py) now joins scenes with a markdown horizontal rule (a new SCENE_SEPARATOR = "\n\n---\n\n") instead of a bare blank line, as a soft visual indicator of scene boundaries in the combined text (no full scene identifiers). Updated test/scene/gui/test_full_story_dialog.py's position-order and skip-unrendered-scene assertions to use SCENE_SEPARATOR accordingly. Full suite (pdm run pytest, 547 tests) and pdm run lint both pass after this change.

### Completed - 2026-08-30T15:08:42Z - John Hoff

Verification passed: pdm run pytest (547 tests, including new test/scene/gui/test_full_story_dialog.py and updated test/scene/gui/test_main_window.py) and pdm run lint both clean. Manual smoke test via a driver script confirmed View Full Story... shows the combined prose (scenes joined by a --- horizontal rule) at the Rendering column's font size, Save... from that dialog writes the correct content to disk, and Save Full Story... saves the same content directly without opening the viewer.
