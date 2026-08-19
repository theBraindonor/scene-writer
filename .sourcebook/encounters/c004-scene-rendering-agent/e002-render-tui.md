---
archived: false
campaign: c004-scene-rendering-agent
created_by: John Hoff
created_on: '2026-08-19T00:52:18Z'
depends_on:
- e001-rendering-pipeline-core
kind: scripted
name: e002-render-tui
regions:
- cli
status: draft
updated_by: John Hoff
updated_on: '2026-08-19T00:52:48Z'
---

# E002 — Render TUI

## Requirements
- Add a `render` command to `scene/cli/coordinator.py` (`scene-coordinator render`) that resolves the rendering agent's `LLMConfig` via `get_llm_config(AgentRole.RENDERING)`, with the same try/except error handling as `chat` (a `RuntimeError`/`TypeError` prints a clear message and exits with code 1), then constructs and runs a new Textual app.
- Add `scene/cli/render_app.py` with a `RenderApp` Textual app: on mount, shows a story picker (a list of existing stories via `scene.core.story.list_stories`, title plus id, no CLI-supplied story id); selecting a story switches to a two-pane render view for that story.
- Two-pane render view: a left-hand pane listing the story's scenes in position order with a rendered/unrendered indicator (based on whether each scene has an active rendering), and showing the currently selected scene's full detail (heading, description, required actions, length, assigned characters, assigned locations) beneath the list; a right-hand pane showing the rendering output area.
- A "Render next scene" action (a bound key and/or button) that: calls `find_next_unrendered_scene`; if `None`, shows a clear "all scenes rendered" notice and makes no generation call; otherwise calls `build_render_messages` for that scene, then `stream_render` in a background worker, streaming `RenderReasoningDelta`/`RenderContentDelta` text live into the right-hand pane via `call_from_thread` (mirroring `CoordinatorApp`'s `@work(thread=True)` streaming pattern), and on `RenderComplete` persists the assembled text via `scene.core.rendering.create_rendering` followed by `set_active_rendering`, then refreshes the left-hand scene list/detail pane to reflect the newly rendered scene.
- Cover the new pipeline-to-TUI wiring with a Textual test (`test/scene/cli/test_render_app.py`, using `App.run_test()` headless, mocking `stream_complete` the same way `test_coordinator_app.py` does) confirming: the story picker lists seeded stories and selecting one shows its scenes; triggering "Render next scene" streams text into the output pane and, once complete, persists an active `Rendering` for the correct scene (verified by reading it back via `scene.core.rendering`); and triggering the action again once every scene is already rendered shows the "all scenes rendered" notice instead of making a generation call.

## Rationale
Delivers the campaign's primary user-visible surface — the first end-to-end path from "no
renderings yet" to "scene 1 is rendered and persisted" — built directly on `e001`'s pipeline
module. Deliberately scoped to only the "render next scene" action; `e003` adds regeneration
and version browsing once this base view and streaming wiring exist. The two-pane layout,
story picker, and streaming-into-a-pane approach follow this campaign's design decisions and
reuse patterns already proven in `scene.cli.coordinator_app.CoordinatorApp` (worker
threading, `call_from_thread`, live-updating panes) without importing from it directly, since
this is an intentionally separate `App`/CLI command per the campaign body.

## Plan
1. Add the `render` command to `scene/cli/coordinator.py`, resolving `LLMConfig` via `get_llm_config(AgentRole.RENDERING)` with the same error handling as `chat`, then constructing and running a new `RenderApp`.
2. Add `scene/cli/render_app.py` with `RenderApp`: a story-picker view backed by `scene.core.story.list_stories`, and, once a story is chosen, the two-pane render view (scene list + detail pane on the left, output pane on the right).
3. Implement the "Render next scene" action: `find_next_unrendered_scene` → (if found) `build_render_messages` → `stream_render` in a background worker, streaming events into the output pane via `call_from_thread`, then on completion `create_rendering` + `set_active_rendering` and refresh the scene list/detail pane; if not found, show a clear notice instead.
4. Add `test/scene/cli/test_render_app.py` covering the story picker, the render-next-scene happy path (streaming plus persistence), and the all-scenes-rendered case, mocking `stream_complete` per the established pattern.
5. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-coordinator render`, pick a story with at least one scene, trigger "Render next scene," confirm the text streams into the output pane, and confirm via `scene-data` that an active rendering was persisted for the correct scene.

## Log
