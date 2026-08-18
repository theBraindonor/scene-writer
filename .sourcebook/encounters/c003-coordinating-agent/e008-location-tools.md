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
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T21:58:25Z'
---

# E008 — Location Tools

## Requirements
- Add tool schemas and dispatch handlers for location data, wired to `scene.core.location` (create, get, list, update, delete) and `scene.core.scene_location` (assign/unassign a location to a scene, list locations for a scene / scenes for a location), following the `e004`/`e006`/`e007` `build_*_tools(state: CoordinatorState)` pattern. `create_location`/`list_locations` take a `story_id`: default it to `state.current_story_id` when omitted, else the same "no current story" error `e005` introduced. `get_location`/`update_location`/`delete_location` operate on an explicit `location_id` (no default, discovered via `list_locations`). `assign_location`/`unassign_location`/`list_locations_for_scene`/`list_scenes_for_location` take explicit `scene_id`/`location_id` arguments; `scene.core.scene_location.assign_location` raises `ValueError` for a missing scene/location or a cross-story pairing — catch it and return a tool-result error, not an unhandled exception.
- Wire the location tool registry into `CoordinatorApp` alongside the existing story, scene, and character tools, completing the coordinator's tool surface for this campaign, using the same `CoordinatorState` instance.
- Extend `_render_story_pane` with two additions, matching the full-detail, two-part treatment `e006`/`e007` settled on after manual verification (not the original "name, briefly" idea this encounter was first drafted with): a "Locations" section (name plus full description, via `scene.core.location.list_locations`) rendered alongside the existing cast-of-characters section; and, within each scene's existing per-scene detail block, a short list of that scene's assigned locations by name (via `scene.core.scene_location.list_locations_for_scene`), matching the existing per-scene "Characters:" line.
- Update `DEFAULT_SYSTEM_PROMPT` in `scene/agent/coordinator/loop.py` to its final form for this campaign, covering all four entities (story, scene, character, location) and their assignments.
- Cover each tool handler with unit tests (including `story_id` defaulting/no-current-story cases and the `ValueError`-to-tool-error handling for assignment), plus an updated Textual test confirming a scripted scenario that creates a location and assigns it to a scene, verifying the location appears both in the pane's Locations section and in that scene's per-scene location list.

## Rationale
Completes the tool-schema-plus-dispatch pattern for the last entity in this campaign's scope,
giving the agent the ability to manage every structural piece of a story's data (excluding
renderings, which remain out of scope) through conversation. Written against the coordinator
as it actually exists after `e005`/`e005a`/`e006`/`e007` — a `CoordinatorState`-driven Textual
TUI with a live right-hand story pane — rather than the CLI-argument/inline-snapshot design this
encounter was originally drafted against. The pane treatment was revised during this review pass
to match precedent actually set by `e006` and `e007`: both were originally planned with brief,
single-line pane entries, and both were expanded post-review, per developer feedback during
manual verification, to full per-entity detail (e006: each scene's description/required
actions/length, not just heading; e007: each character's description/motive, not just name)
plus, for characters, a per-scene assigned-character line. This encounter is written directly
against that settled pattern up front, rather than drafting the brief version and expecting the
same deviation again.

## Plan
1. Add a `scene/agent/coordinator/tools/location.py` module with tool schemas and handlers wired to `scene.core.location` and `scene.core.scene_location`, each opening its own `session_scope()`, with `create_location`/`list_locations` resolving `story_id` the same way `e005`'s story tools do, and assignment handlers catching `ValueError` into a tool-result error.
2. Update `scene/cli/coordinator_app.py`'s `CoordinatorApp.__init__` to build and combine the location tool registry with the existing story/scene/character registries (all built from `self.state`).
3. Update `_render_story_pane` to add a "Locations" section (name + description, via `scene.core.location.list_locations`), and to extend each scene's existing detail block with a line listing that scene's assigned locations by name (via `scene.core.scene_location.list_locations_for_scene`, one call per scene), matching the existing per-scene "Characters:" line.
4. Update `DEFAULT_SYSTEM_PROMPT` to its final form for this campaign, covering all four entities and their assignments.
5. Add tests under `test/scene/agent/coordinator/tools/test_location.py` (mirroring the established pattern), and extend `test/scene/cli/test_coordinator_app.py` with a scripted create-and-assign scenario asserting the location shows up in both the Locations section and its assigned scene's location list.
6. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-coordinator chat` and drive a short conversation that touches story, scene, character, and location tools, confirming the right-hand story pane reflects all of it correctly, including a location's full detail in the top-level Locations section and its name in its assigned scene's location list.

## Log

### Review - 2026-08-18T21:48:11Z - John Hoff

Reviewed against the two applicable lore items (linting, unit-testing), both world-assigned: the Plan explicitly runs and requires zero ruff lint errors (Plan step 6, Verification), and explicitly requires new/updated pytest unit tests mirroring src/ under test/ (Plan steps 5-6, Verification), correctly placing the new location-tools test at test/scene/agent/coordinator/tools/test_location.py to mirror the new src/scene/agent/coordinator/tools/location.py module. Spot-checked the encounter's factual claims within its cited surface (scene.core.location, scene.core.scene_location, the build_*_tools(state: CoordinatorState) pattern in story.py/scene.py/character.py, and _render_story_pane/DEFAULT_SYSTEM_PROMPT in coordinator_app.py/coordinator/loop.py) and found the Plan grounded in the codebase as it actually exists post-e005/e006/e007, including the revised full-detail story-pane treatment the Rationale describes. No lore conflicts found. PASS-WITH-NOTES.

### Completed - 2026-08-18T21:58:25Z - John Hoff

Verified: pdm run pytest passes 264/264 with 100% coverage, pdm run lint zero errors. Delivered scene/agent/coordinator/tools/location.py (build_location_tools: create/get/list/update/delete_location plus assign_location/unassign_location/list_locations_for_scene/list_scenes_for_location, story_id defaulting to current story for create_location/list_locations, ValueError-to-tool-error handling for missing scene/location and cross-story assignment, clear errors for missing location_id/scene_id); CoordinatorApp now combines story, scene, character, and location tool registries off the same CoordinatorState, completing the campaign's tool surface; _render_story_pane now has a Locations section (name + description) and a per-scene Locations line, matching the established Cast-of-characters/per-scene-Characters pattern; DEFAULT_SYSTEM_PROMPT updated to its final form covering all four entities and their scene assignments. Developer manually verified against the live LM Studio server via scene-coordinator chat, confirming location creation and scene assignment appear in the agent's reply and the right-hand pane.
