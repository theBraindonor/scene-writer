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
updated_on: '2026-08-18T15:03:53Z'
---

# E008 — Location Tools

## Requirements
- Add tool schemas and dispatch handlers for location data, wired to `scene.core.location` (create, get, list, update, delete) and `scene.core.scene_location` (assign/unassign a location to a scene, list locations for a scene / scenes for a location), following the `e004`/`e006`/`e007` pattern.
- Wire the location tool registry into `scene-coordinator chat` alongside the existing story, scene, and character tools, completing the coordinator's tool surface for this campaign.
- Update the default system prompt to describe the coordinator's ability to manage the story's locations and assign them to scenes, finalizing the prompt to reflect the coordinator's full editing capability (story, scene, character, location, and their assignments).
- Cover each tool handler with unit tests, plus an updated CLI test confirming a scripted scenario that creates a location and assigns it to a scene, verifying both appear in the `e005` state-display snapshot.

## Rationale
Completes the tool-schema-plus-dispatch pattern for the last entity in this campaign's scope,
giving the agent the ability to manage every structural piece of a story's data (excluding
renderings, which remain out of scope) through conversation.

## Plan
1. Add a `scene/agent/coordinator/tools/location.py` module with tool schemas and handlers wired to `scene.core.location` and `scene.core.scene_location`, each opening its own `session_scope()` and scoping to the REPL's `story_id` where applicable.
2. Update `scene/cli/coordinator.py`'s `chat` command to include the location tool registry.
3. Update the default system prompt to its final form for this campaign, covering all four entities and their assignments.
4. Add tests under `test/scene/agent/coordinator/tools/test_location.py`, and extend `test/scene/cli/test_coordinator.py` with a scripted create-and-assign scenario.
5. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `scene-coordinator chat <story_id>` and drive a short conversation that touches story, scene, character, and location tools, confirming the state snapshot reflects all of it correctly.

## Log
