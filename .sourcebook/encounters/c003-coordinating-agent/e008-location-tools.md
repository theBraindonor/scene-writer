---
archived: false
campaign: c003-coordinating-agent
created_by: John Hoff
created_on: '2026-08-18T15:03:25Z'
depends_on:
- e007-character-tools
kind: scripted
name: e008-location-tools
regions:
- agent
- cli
status: draft
updated_by: John Hoff
updated_on: '2026-08-18T18:33:02Z'
---

# E008 — Location Tools

## Requirements
- Add tool schemas and dispatch handlers for location data, wired to `scene.core.location` (create, get, list, update, delete) and `scene.core.scene_location` (assign/unassign a location to a scene, list locations for a scene / scenes for a location), following the `e004`/`e006`/`e007` `build_*_tools(state: CoordinatorState)` pattern. `create_location`/`list_locations` take a `story_id`: default it to `state.current_story_id` when omitted, else the same "no current story" error `e005` introduced. `get_location`/`update_location`/`delete_location` operate on an explicit `location_id` (no default, discovered via `list_locations`). `assign_location`/`unassign_location`/`list_locations_for_scene`/`list_scenes_for_location` take explicit `scene_id`/`location_id` arguments; `scene.core.scene_location.assign_location` raises `ValueError` for a missing scene/location or a cross-story pairing — catch it and return a tool-result error, not an unhandled exception.
- Wire the location tool registry into `CoordinatorApp` alongside the existing story, scene, and character tools, completing the coordinator's tool surface for this campaign, using the same `CoordinatorState` instance.
- Extend `_render_story_pane` to also list the current story's locations (name, briefly) alongside its scenes and characters.
- Update `DEFAULT_SYSTEM_PROMPT` in `scene/agent/coordinator/loop.py` to its final form for this campaign, covering all four entities (story, scene, character, location) and their assignments.
- Cover each tool handler with unit tests (including `story_id` defaulting/no-current-story cases and the `ValueError`-to-tool-error handling for assignment), plus an updated Textual test confirming a scripted scenario that creates a location and assigns it to a scene, verifying both appear in the right-hand story pane.

## Rationale
Completes the tool-schema-plus-dispatch pattern for the last entity in this campaign's scope,
giving the agent the ability to manage every structural piece of a story's data (excluding
renderings, which remain out of scope) through conversation. Written against the coordinator
as it actually exists after `e005`/`e005a`/`e006`/`e007` — a `CoordinatorState`-driven Textual
TUI with a live right-hand story pane — rather than the CLI-argument/inline-snapshot design this
encounter was originally drafted against.

## Plan
1. Add a `scene/agent/coordinator/tools/location.py` module with tool schemas and handlers wired to `scene.core.location` and `scene.core.scene_location`, each opening its own `session_scope()`, with `create_location`/`list_locations` resolving `story_id` the same way `e005`'s story tools do, and assignment handlers catching `ValueError` into a tool-result error.
2. Update `scene/cli/coordinator_app.py`'s `CoordinatorApp.__init__` to build and combine the location tool registry with the existing story/scene/character registries (all built from `self.state`).
3. Update `_render_story_pane` to its final form, also rendering the current story's locations.
4. Update `DEFAULT_SYSTEM_PROMPT` to its final form for this campaign, covering all four entities and their assignments.
5. Add tests under `test/scene/agent/coordinator/tools/test_location.py` (mirroring the established pattern), and extend `test/scene/cli/test_coordinator_app.py` with a scripted create-and-assign scenario.
6. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-coordinator chat` and drive a short conversation that touches story, scene, character, and location tools, confirming the right-hand story pane reflects all of it correctly.

## Log
