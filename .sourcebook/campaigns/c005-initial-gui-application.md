---
archived: false
created_by: John Hoff
created_on: '2026-08-20T21:58:36Z'
name: c005-initial-gui-application
status: completed
updated_by: John Hoff
updated_on: '2026-08-21T20:42:31Z'
---

# C005 — Initial GUI Application

## Scope

Build the first version of Scene Writer's unified GUI — the long-term goal `README.md` and
`src/scene/gui` (a placeholder package since `c001`) have pointed at since the project's start —
as a desktop application launched via a new `scene-writer` console script, built with PySide6.

The window layout has four regions:

- A **collapsible far-left sidebar** for picking (and creating) the story to view/edit.
- A **main entity column** (view/edit column) showing the selected story's structural data —
  scenes, cast, locations, and their assignments — with full create/edit/delete capability,
  matching everything the coordinating agent's tools can already do.
- A **rendering column** to the entity column's right, showing the currently selected scene's
  active rendering, read-only.
- A **full-width chat panel** docked at the bottom, driving the same coordinating agent
  (`scene.agent.coordinator`) the existing `scene-coordinator chat` TUI uses, so a writer can
  ask the agent to make changes instead of (or alongside) editing directly.

Out of scope for this campaign: generating or regenerating scene prose from the GUI (the
rendering column is view-only; generation stays on `scene-coordinator render` for now — a
GUI-side render/regenerate flow is expected to follow in a later campaign once this shell is in
place), and any redesign of the `scene.core`/`scene.data`/`scene.agent` layers — this campaign is
purely a new UI consumer of those existing services, exactly as `c004` was for rendering.

## Design decisions

- **PySide6, launched via a new `scene-writer` console script.** A new dependency
  (`PySide6`) and a new `[project.scripts]` entry (`scene-writer = "scene.gui.app:main"`) sit
  alongside the existing Typer-based scripts (`scene-data`, `scene-coordinator`); `main()`
  constructs a `QApplication`, builds the main window, and calls `app.exec()`. `pytest-qt` is
  added as a new dev dependency so the GUI gets the same unit-test coverage every other package
  has (its `qtbot` fixture plays the same role Textual's `run_test()`/`Pilot` already does for
  the two existing TUIs).
- **Reuses the coordinating agent as-is — no new agent code.** The chat panel drives
  `scene.agent.coordinator.loop.run_turn` against the existing `CoordinatorState` and the
  existing tool builders (`build_story_tools`/`build_scene_tools`/`build_character_tools`/
  `build_location_tools`) from `c003`, unchanged. The GUI is a second consumer of that same
  agent loop, the same way `CoordinatorApp` (Textual) is today — no new tool, prompt, or
  agent-state surface is introduced.
- **Direct entity edits and chat-driven edits share one code path and one story of truth.**
  Both the entity column's create/edit/delete actions and the chat agent's tools call straight
  through to `scene.core`'s existing CRUD functions (`scene.core.story`/`scene.core.scene`/
  `scene.core.character`/`scene.core.location`/`scene.core.scene_character`/
  `scene.core.scene_location`) against a fresh `session_scope()` per operation — the same
  pattern every existing CLI already follows. Direct SQLite calls run synchronously on the Qt
  main thread (they're fast, single-row operations, matching how `RenderApp`'s
  activate/delete-version handlers already call `session_scope()` inline without a background
  thread); only the LLM chat turn is backgrounded (see below).
- **Two-way story sync between the sidebar and the chat agent.** Selecting a story in the
  sidebar sets `CoordinatorState.current_story_id` directly and refreshes the entity and
  rendering columns to match — no tool call involved. Conversely, because
  `build_story_tools`' handlers already mutate `state.current_story_id` whenever the agent
  creates, selects, or archives a story (see `scene/agent/coordinator/tools/story.py`), the GUI
  re-reads `state.current_story_id` after every completed chat turn and, if it changed,
  updates the sidebar's selection and refreshes the entity/rendering columns to follow —
  mirroring exactly how `CoordinatorApp._refresh_story_pane` already re-reads that same field
  after every turn today. No changes to the tool layer are needed for either direction.
- **Background threading and cross-thread updates use Qt's own primitives, not asyncio.**
  `run_turn` is a plain synchronous generator (as `stream_complete`/`stream_render` are
  throughout this codebase) — it runs on a `QThread` (or a plain `threading.Thread`), and each
  yielded `TurnEvent` is delivered to the main thread via a Qt signal/slot (queued connection),
  the direct Qt equivalent of the `@work(thread=True)` + `call_from_thread` pattern already
  used by both `CoordinatorApp` and `RenderApp`. No `asyncio`/`qasync` bridging is introduced;
  none of the existing LLM-runtime code is `asyncio`-based.
- **Collapsible sidebar via a resizable splitter, not a dock widget.** The far-left story
  picker is a pane of a `QSplitter`, collapsed by driving its size to zero (and restored to its
  last width) rather than a `QDockWidget` — the developer described it as a "column," and a
  splitter pane keeps it a fixed part of the main window's layout rather than letting it float
  or detach the way a dock widget would.
- **Rendering column is read-only for this campaign.** It shows the selected scene's current
  active rendering (or a placeholder if none exists yet, mirroring `RenderApp`'s
  `NO_RENDERINGS_TEXT`-style empty states) by reading `scene.core.rendering` directly — no
  streaming, no generate/regenerate actions, and no version browsing here yet. Per the
  developer's direction at `c004`'s close, further rendering-workflow UI is expected to land in
  the GUI in a later campaign rather than the TUI; this campaign only lays the groundwork
  (the column exists and displays correctly) without pulling that whole workflow in at once.

## Log

### Completed - 2026-08-21T20:42:31Z - John Hoff

All seven encounters delivered: the PySide6 app skeleton with collapsible sidebar (e001), full entity-column CRUD (e002), a read-only rendering column (e003), chat-panel integration with the coordinating agent (e004), README documentation (e005), and a follow-up layout rework replacing the sidebar with a story header + tabbed entity column and a draggable fifty-fifty left/right split with the chat panel (e006, e007). The GUI shell is now at a steady-state logical layout. Per the developer's direction at close-out, further work moves to a new campaign (c006-gui-usability) focused on streamlining the existing components into a fully usable application — starting with bringing the rendering column's create/browse/activate workflow (currently only available via `scene-coordinator render`) into the GUI, as this campaign's scope explicitly deferred.
