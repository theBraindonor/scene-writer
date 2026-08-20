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
status: draft
updated_by: John Hoff
updated_on: '2026-08-20T22:46:30Z'
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
