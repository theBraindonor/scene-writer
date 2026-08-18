---
archived: false
campaign: c003-coordinating-agent
created_by: John Hoff
created_on: '2026-08-18T15:03:15Z'
depends_on:
- e005-coordinator-cli-state-display
kind: scripted
name: e006-scene-tools
regions:
- agent
- cli
status: draft
updated_by: John Hoff
updated_on: '2026-08-18T15:03:52Z'
---

# E006 — Scene Tools

## Requirements
- Add tool schemas and dispatch handlers for scene data, wired to `scene.core.scene`: create, get, list, update, and delete — following the same pattern established in `e004-story-tools` (own `session_scope()` per handler, JSON-serializable results, scoped to the REPL's story where the underlying `scene.core` functions require a `story_id`).
- Wire the scene tool registry into `scene-coordinator chat` alongside the story tools from `e004`.
- Update the default system prompt to describe the coordinator's ability to view and edit the story's scenes (heading, description, required actions, length, position), in addition to story-level fields.
- Cover each tool handler with unit tests verifying it calls the correct `scene.core.scene` function and shapes its result correctly, plus an updated CLI test confirming a scripted tool-call round trip creates/updates a scene and that it appears in the `e005` state-display snapshot.

## Rationale
Extends the tool-schema-plus-dispatch pattern from `e004-story-tools` to scenes, the next entity
in the data model, giving the agent the ability to build up a story's ordered scene list through
conversation.

## Plan
1. Add a `scene/agent/coordinator/tools/scene.py` module with tool schemas and handlers wired to `scene.core.scene`, each opening its own `session_scope()` and scoping to the REPL's `story_id`.
2. Update `scene/cli/coordinator.py`'s `chat` command to include the scene tool registry alongside the story tools.
3. Update the default system prompt to mention scene-editing capability.
4. Add tests under `test/scene/agent/coordinator/tools/test_scene.py`, and extend `test/scene/cli/test_coordinator.py` with a scripted scene-creation scenario, asserting the resulting snapshot output includes the new scene.
5. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `scene-coordinator chat <story_id>` and ask the agent to add a scene, confirming it appears both in the agent's reply and in the printed state snapshot.

## Log
