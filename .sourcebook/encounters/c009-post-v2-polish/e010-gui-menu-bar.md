---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-30T05:27:40Z'
depends_on: []
kind: unscripted
name: e010-gui-menu-bar
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-30T05:29:51Z'
---

## Requirements

Added a menu bar to the PySide6 GUI's `MainWindow` (`src/scene/gui/main_window.py`):

- **File** — `New Story...` and `Open Story...`, wired to trigger the existing `StoryHeader.new_story_button` / `open_button` (`story_header.new_story_button.click()` / `.open_button.click()`) rather than duplicating dialog logic, plus `Exit` (calls `self.close()`).
- **Render** — `View Full Story...` and `Export Full Story...`, both placeholders for not-yet-built functionality; each shows a `QMessageBox.information(..., "Not yet implemented.")`.
- **Help** — `About Scene Writer`, opening a new modal `AboutDialog`.

Added `src/scene/gui/about_dialog.py`: a new `AboutDialog(QDialog)` showing the application name ("Scene Writer"), its installed version (resolved via `importlib.metadata.version("scene-writer")`, falling back to `"development"` if package metadata isn't found), and a short description of what Scene Writer does, with a single OK button.

Test coverage added:
- `test/scene/gui/test_main_window.py` — new tests asserting the three top-level menus exist; that File > New Story / Open Story drive the same `StoryHeader` prompt-and-create/prompt-and-open flow already covered by the header's own tests (monkeypatching `_prompt_new_story` / `_prompt_story_picker` as the existing header tests do); that File > Exit closes the window; that the two Render placeholders each show a `QMessageBox.information` with "Not yet implemented."; and that Help > About opens an `AboutDialog`.
- `test/scene/gui/test_about_dialog.py` (new) — asserts the dialog shows the app name, the resolved version string, a wrapped description mentioning "Scene Writer", and that its OK button accepts the dialog.

Full suite (`pdm run pytest`, 532 tests) and `pdm run lint` both pass after these changes.

## Rationale

This is the first navigational chrome in the GUI (previously just the splitter-based story header / entity column / chat / rendering layout with no menu bar at all). The user asked for File, Render, and Help menus as the next incremental step in the GUI's development: File to expose the existing new/open story flows (plus a way to exit) through a conventional desktop-app entry point, Render to reserve a visible home for full-story viewing/export before those features are built, and Help to give the app a standard About dialog.

The File actions reuse `StoryHeader`'s existing buttons/handlers instead of re-implementing story creation/selection so there is exactly one code path for each and the menu items can't drift out of sync with the toolbar buttons. The Render actions are intentionally inert placeholders — the underlying "view full story" and "export full story" features don't exist yet — so the menu communicates the app's intended shape without pretending to deliver on it early. The About dialog reads its version from installed package metadata rather than hardcoding it, so it can't silently go stale as `pyproject.toml`'s version is bumped.

## Log

### Review - 2026-08-30T05:28:57Z - John Hoff

Reviewed e010-gui-menu-bar (unscripted): the Requirements/Rationale are concrete and specific, and spot-checking the two files they name (src/scene/gui/main_window.py's _build_menu_bar/placeholder handlers and the new src/scene/gui/about_dialog.py) confirms the recorded work matches what's described — File actions delegate to StoryHeader's existing buttons rather than duplicating logic, Render actions are honest placeholders, and AboutDialog resolves its version from installed package metadata with a sensible fallback. Both applicable world lore items are honored: linting (ruff, 120-char) and unit-testing (new test files under test/scene/gui/ correctly mirroring the two new/changed source modules, with the full suite and lint reported passing). No lore conflicts found; the only aside is that the gui region's own summary ('Not yet implemented') is now stale given this and recent prior GUI work, which is a region-documentation nit rather than a defect in this encounter. PASS-WITH-NOTES.

### Completed - 2026-08-30T05:29:51Z - John Hoff

Recorded work confirmed accurate on review; no follow-up actions raised. Menu bar (File/Render/Help) and About dialog are in place, tested, and passing lint/tests.
