---
archived: false
created_by: John Hoff
created_on: '2026-08-21T20:42:41Z'
name: c006-gui-usability
status: completed
updated_by: John Hoff
updated_on: '2026-08-23T22:25:50Z'
---

# C006 — GUI Usability

## Scope

`c005-initial-gui-application` established the GUI's logical layout — story header, tabbed
entity column, chat panel, rendering column — at a steady state. This campaign does not change
that structure and does not add new raw story-domain functionality (no new entity types, no new
agent capabilities, no `scene.core`/`scene.data`/`scene.agent` redesign). Instead it closes the
remaining gaps between what the GUI currently *displays* and what the existing CLI/TUI surfaces
(`scene-data`, `scene-coordinator render`) can already *do*, so the GUI becomes a fully usable
application in its own right rather than a read-only companion that still requires dropping back
to a TUI for real work.

First target: the rendering column. It is currently read-only (an explicit, named deferral in
c005's own scope) — it shows a scene's active rendering but offers no way to create, browse
version history, switch the active version, or delete a rendering from the GUI; every one of
those actions still requires `scene-coordinator render`. Bringing that workflow into the GUI,
mirroring the existing `RenderApp` TUI (`src/scene/cli/render_app.py`), is this campaign's first
encounter. Later encounters are expected to close similar gaps elsewhere in the GUI as they're
identified, under the same "usability, not new functionality" constraint.

## Design decisions

- **No changes to `scene.core`/`scene.data`/`scene.agent`.** Every increment in this campaign is
  a new UI consumer of already-existing services — the same constraint c005 held itself to for
  the entity column and the (read-only) rendering column.
- **Mirror existing CLI/TUI behavior rather than redesigning it.** Where a Textual TUI already
  has a working, proven answer — e.g. `RenderApp`'s version list ordering (`v{index}` via
  `list_renderings()`'s id order; there is no explicit version-number column), its guardrails
  against deleting the sole or active rendering, its render-next-vs-regenerate distinction, and
  its streamed generation with cancel support — the GUI should reproduce that behavior rather
  than inventing new UX, using Qt's `QThread`/signal pattern already established by
  `chat_panel.py`'s `_TurnWorker` in place of Textual's `@work(thread=True)` /
  `call_from_thread`.

## Log

### Completed - 2026-08-23T22:25:50Z - John Hoff

Delivered the campaign's first (and, for now, only) targeted gap: full rendering-column management in the GUI (e001-rendering-column-management) — version browsing with an active marker, activate/delete with sole/active guardrails, streamed Render/Regenerate with a "Preview Prompt" dialog and Cancel, guaranteed save-on-completion (including on cancel or stream error), a larger body font, and auto-scroll while streaming, all mirroring the proven RenderApp TUI workflow with no changes to scene.core/scene.data/scene.agent. Closing the campaign now, with the developer's direction that a fair amount of hands-on testing has been completed and the project is moving to an application-wide refactoring pass next. Further GUI-usability gaps identified later can open a new campaign when that work resumes.
