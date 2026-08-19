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
status: completed
updated_by: John Hoff
updated_on: '2026-08-19T04:02:29Z'
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

### Review - 2026-08-19T03:25:11Z - John Hoff

Reviewed e002-render-tui against the linting and unit-testing lore and against c004's design decisions: both lore items are explicitly honored (Plan step 5 and Verification require pdm run lint clean and pdm run pytest green, with the new test correctly placed at test/scene/cli/test_render_app.py mirroring src/scene/cli/render_app.py). The Plan's technical claims check out against the real code they cite: find_next_unrendered_scene, build_render_messages, stream_render, and the RenderReasoningDelta/RenderContentDelta/RenderComplete event shapes all match src/scene/agent/rendering.py as delivered in the completed e001, and the "same try/except error handling as chat" and "mirrors CoordinatorApp's @work(thread=True)/call_from_thread streaming pattern" claims both match the actual coordinator.py/coordinator_app.py code, with the new RenderApp correctly kept as a separate, non-importing App per the campaign's stated design. The no-CLI-story-id, in-TUI story-picker approach matches the campaign's design decision verbatim, and scoping this encounter to only "render next scene" (deferring regeneration and version browsing to e003) is an explicit, reasonable phasing of the campaign's broader two-pane/version-browsing design rather than a contradiction of it. scene.core.story.list_stories and scene.core.rendering.create_rendering/set_active_rendering were confirmed to exist with the assumed shapes, and test_coordinator_app.py's stream_complete-mocking convention is a real, reusable pattern. PASS-WITH-NOTES.

### Message - 2026-08-19T03:57:38Z - John Hoff

Deviation from the reviewed Plan, per developer feedback after the first manual pass at the render TUI: the output pane didn't auto-scroll as streamed text arrived, so long generations scrolled out of view. Added a scroll_end(animate=False) call on the output VerticalScroll in _append_output, mirroring CoordinatorApp's existing per-event auto-scroll pattern from e005a. Added test_output_pane_auto_scrolls_on_every_streamed_chunk to test/scene/cli/test_render_app.py (spying on VerticalScroll.scroll_end, mirroring test_coordinator_app.py's equivalent test). pdm run pytest (288/288, 100% coverage) and pdm run lint (zero errors) both pass after the change.

### Completed - 2026-08-19T04:02:29Z - John Hoff

Verified: pdm run pytest passes 288/288 with 100% coverage, pdm run lint zero errors. Delivered scene/cli/render_app.py: StoryPickerScreen (lists stories via scene.core.story.list_stories, click to select, no CLI-supplied story id) and RenderScreen (a two-pane view: scene list with rendered/unrendered indicators plus the selected scene's full detail on the left, streaming output pane on the right). "Render next scene" resolves find_next_unrendered_scene, builds context via build_render_messages, streams via stream_render in a background worker (mirroring CoordinatorApp's @work(thread=True)/call_from_thread pattern), and on RenderComplete persists via create_rendering + set_active_rendering, then refreshes the scene pane. The all-scenes-rendered case shows a clear notice with no generation call. Added the scene-coordinator render command to coordinator.py, resolving AgentRole.RENDERING with the same error handling as chat. Developer manually verified against the live LM Studio server, confirming streaming output and persistence. Per developer feedback during manual verification, the output pane was fixed to auto-scroll on every streamed chunk (mirroring CoordinatorApp's e005a auto-scroll pattern) — recorded as a deviation message and covered by a new regression test.
