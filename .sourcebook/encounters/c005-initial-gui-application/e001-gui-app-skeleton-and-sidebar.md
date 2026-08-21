---
archived: false
campaign: c005-initial-gui-application
created_by: John Hoff
created_on: '2026-08-20T22:30:04Z'
depends_on: []
kind: scripted
name: e001-gui-app-skeleton-and-sidebar
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-21T01:37:57Z'
---

# E001 — GUI App Skeleton and Story Sidebar

## Requirements
- Add `PySide6` to `[project.dependencies]` and `pytest-qt` to the `dev` group in
  `[project.optional-dependencies]` in `pyproject.toml`, and register a new console script,
  `scene-writer = "scene.gui.app:main"`, alongside the existing `scene-data`/`scene-coordinator`
  entries.
- Build `scene.gui.app` with a `main()` that constructs a `QApplication`, builds and shows the
  main window, and calls `app.exec()` — the `scene-writer` entry point.
- Build a `MainWindow` (`QMainWindow`) implementing the campaign's four-region skeleton: a
  horizontal `QSplitter` with three panes (collapsible sidebar, entity column, rendering
  column), and the chat panel docked below it at full width. For this encounter, the entity
  column, rendering column, and chat panel are empty placeholders (e.g. a `QLabel` naming the
  region) — only the sidebar is functional; later encounters (`e002`–`e004`) fill the other
  three in.
- Build the sidebar as its own widget: lists existing (non-archived) stories via
  `scene.core.story.list_stories`, lets the user select one, lets the user create a new story
  (title, scenario, optional style guidance) via `scene.core.story.create_story` (refreshing
  the list and selecting the new story), and offers a collapse/expand toggle that drives the
  sidebar pane's `QSplitter` size to/from zero (restoring its prior width on expand), per the
  campaign's splitter-based collapse design.
- Track the selected story as `current_story_id` on the main window, and emit a Qt signal
  (e.g. `current_story_changed(int | None)`) whenever it changes, whether from a user selection
  or a newly created story — this is the interface contract later encounters (`e002` entity
  column, `e003` rendering column, `e004` chat integration) connect to; no other pane reacts to
  it yet in this encounter.
- Cover the sidebar's behavior with tests in `test/scene/gui/test_main_window.py`, using
  `pytest-qt`'s `qtbot` fixture: the story list reflects what's in the database, selecting a
  story sets `current_story_id` and emits the signal, creating a story adds and selects it, and
  the collapse toggle drives the sidebar pane's width to zero and back.

## Rationale
Establishes the application shell and its console script once, so every later encounter in
this campaign (`e002` entity column, `e003` rendering column, `e004` chat integration) has a
running window and a selected-story concept to build against, rather than each re-deriving its
own bootstrap. The sidebar is built now rather than deferred because every other pane depends
on "which story is selected" existing first, and a Qt signal is the idiomatic way those later
panes react to it without polling. `PySide6` and `pytest-qt` are added once, here, as the
campaign's foundational dependencies — no later encounter should need to touch `pyproject.toml`
for GUI tooling again.

## Plan
1. Add `PySide6` and `pytest-qt` to `pyproject.toml` (`dependencies` and the `dev` optional
   group respectively) and the `scene-writer` console script entry; run `pdm install -G dev` so
   the console script registers.
2. Create `src/scene/gui/app.py` with `main()` (constructs `QApplication`, `MainWindow`, calls
   `.show()` then `app.exec()`).
3. Create `src/scene/gui/main_window.py` with `MainWindow(QMainWindow)`: the horizontal
   `QSplitter` skeleton (sidebar / entity placeholder / rendering placeholder) and the chat
   placeholder docked below it, plus a `current_story_id: int | None` attribute and a
   `current_story_changed` signal.
4. Create `src/scene/gui/sidebar.py` (or a class within `main_window.py` if it stays small)
   implementing the story list, select, create-story form, and collapse/expand toggle described
   in Requirements, calling `scene.core.story` directly against `session_scope()`, and emitting
   `current_story_changed` on every selection change.
5. Add `test/scene/gui/test_main_window.py` covering the sidebar behaviors in Requirements,
   using `pytest-qt`'s `qtbot` fixture and the existing `isolated_database` monkeypatch pattern
   (see `test/scene/cli/test_render_app.py`) so tests run against a temporary database. Note in
   the test module (or a `conftest.py`) that headless runs need `QT_QPA_PLATFORM=offscreen` if
   no display is available.
6. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-writer`: confirm the window opens with the sidebar, entity
  placeholder, rendering placeholder, and chat placeholder all visible; confirm the sidebar
  lists existing stories, creating a new story adds and selects it, and the collapse toggle
  hides and restores the sidebar pane.

## Log

### Review - 2026-08-21T01:14:38Z - John Hoff

Reviewed against the two applicable lore items (linting, unit-testing): the Plan satisfies both — `pdm run lint` and `pdm run pytest` are run and required to pass per Verification. One structural gap: Plan step 4 leaves the sidebar's home ambiguous between a new `sidebar.py` module or a class folded into `main_window.py`, but step 5 commits to a single fixed test file (`test/scene/gui/test_main_window.py`) regardless — if the sidebar lands in its own module, this would leave its tests not mirroring unit-testing lore's module-to-test-path convention. Recommend resolving the sidebar's module location before/during implementation and naming the matching test file accordingly (`test_sidebar.py` if split out). Not blocking — pass with this note.

### Message - 2026-08-21T01:37:25Z - John Hoff

Verification: `pdm run pytest` (307 passed, incl. 11 new tests in test/scene/gui/) and `pdm run lint` (zero errors) both pass. Manually launched `pdm run scene-writer` as a real process and confirmed via screenshots: the window opens with all four regions visible (sidebar with Collapse toggle/story list/New Story button, Entity Column placeholder, Rendering Column placeholder, Chat Panel placeholder); the sidebar lists the existing story from the local dev database; the Collapse/Expand toggle drives the sidebar pane's splitter width to zero and restores it, confirmed live via screenshots both directions; the New Story dialog opens with Title/Scenario/Style Guidance fields and OK/Cancel, and accepts typed input correctly. Synthetic mouse clicks on the dialog's OK button were not reliably deliverable in this remote desktop environment (a KVM/Synergy input-sharing tool is active on the machine) despite the cursor landing on-target per GetCursorPos, so the OK-submit step of story creation was verified via the automated pytest-qt suite instead (test_creating_story_adds_and_selects, test_creating_story_via_sidebar_updates_window), which exercises the identical code path (dialog values -> create_story -> refresh_stories -> select and signal emission) through Qt's own test event delivery. Also noted and fixed during implementation: the collapse toggle button was originally laid out inside the Sidebar's own collapsible widget, which meant collapsing the pane to zero width also made the toggle unclickable to expand again — moved the button into an always-visible header row above the splitter (scene/gui/main_window.py) so it stays reachable regardless of collapse state. Per the earlier review note, the sidebar landed in its own module (scene/gui/sidebar.py) and its tests are in the mirrored test/scene/gui/test_sidebar.py, separate from test/scene/gui/test_main_window.py.

### Completed - 2026-08-21T01:37:57Z - John Hoff

All tests pass (307/307) and lint is clean. Manually verified the live app: window opens with all four regions, sidebar lists real story data, collapse/expand toggle confirmed working in both directions, and New Story dialog opens with correct fields and accepts input (dialog OK-submit verified via the equivalent automated pytest-qt path per the note above, due to click-automation limits in this environment). Fixed a real collapse-toggle-unclickable-when-collapsed bug found during manual verification.
