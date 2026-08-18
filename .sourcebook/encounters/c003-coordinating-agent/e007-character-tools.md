---
archived: false
campaign: c003-coordinating-agent
created_by: John Hoff
created_on: '2026-08-18T15:03:20Z'
depends_on:
- e006-scene-tools
kind: scripted
name: e007-character-tools
regions:
- agent
- cli
status: draft
updated_by: John Hoff
updated_on: '2026-08-18T15:03:53Z'
---

# E007 — Character Tools

## Requirements
- Add tool schemas and dispatch handlers for character data, wired to `scene.core.character` (create, get, list, update, delete) and `scene.core.scene_character` (assign/unassign a character to a scene, list characters for a scene / scenes for a character), following the `e004`/`e006` pattern.
- Wire the character tool registry into `scene-coordinator chat` alongside the existing story and scene tools.
- Update the default system prompt to describe the coordinator's ability to manage the story's cast of characters and assign them to scenes.
- Cover each tool handler with unit tests, plus an updated CLI test confirming a scripted scenario that creates a character and assigns it to a scene, verifying both appear in the `e005` state-display snapshot.

## Rationale
Extends the established tool-schema-plus-dispatch pattern to characters and their scene
assignments, the next entities in the data model, giving the agent the ability to build a
story's cast and place them in scenes through conversation.

## Plan
1. Add a `scene/agent/coordinator/tools/character.py` module with tool schemas and handlers wired to `scene.core.character` and `scene.core.scene_character`, each opening its own `session_scope()` and scoping to the REPL's `story_id` where applicable.
2. Update `scene/cli/coordinator.py`'s `chat` command to include the character tool registry.
3. Update the default system prompt to mention character/cast-assignment capability.
4. Add tests under `test/scene/agent/coordinator/tools/test_character.py`, and extend `test/scene/cli/test_coordinator.py` with a scripted create-and-assign scenario.
5. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `scene-coordinator chat <story_id>` and ask the agent to add a character and assign it to an existing scene, confirming both actions are reflected in the reply and the state snapshot.

## Log
