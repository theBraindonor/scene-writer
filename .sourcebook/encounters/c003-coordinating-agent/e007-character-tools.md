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
updated_on: '2026-08-18T18:32:53Z'
---

# E007 — Character Tools

## Requirements
- Add tool schemas and dispatch handlers for character data, wired to `scene.core.character` (create, get, list, update, delete) and `scene.core.scene_character` (assign/unassign a character to a scene, list characters for a scene / scenes for a character), following the `e004`/`e006` `build_*_tools(state: CoordinatorState)` pattern. `create_character`/`list_characters` take a `story_id`: default it to `state.current_story_id` when omitted, else the same "no current story" error `e005` introduced. `get_character`/`update_character`/`delete_character` operate on an explicit `character_id` (no default, discovered via `list_characters`). `assign_character`/`unassign_character`/`list_characters_for_scene`/`list_scenes_for_character` take explicit `scene_id`/`character_id` arguments; `scene.core.scene_character.assign_character` raises `ValueError` for a missing scene/character or a cross-story pairing — catch it and return a tool-result error, not an unhandled exception.
- Wire the character tool registry into `CoordinatorApp` alongside the existing story and scene tools, using the same `CoordinatorState` instance.
- Extend `_render_story_pane` to also list the current story's characters (name, briefly) alongside its scenes.
- Update `DEFAULT_SYSTEM_PROMPT` in `scene/agent/coordinator/loop.py` to describe the coordinator's ability to manage the story's cast of characters and assign them to scenes.
- Cover each tool handler with unit tests (including `story_id` defaulting/no-current-story cases and the `ValueError`-to-tool-error handling for assignment), plus an updated Textual test confirming a scripted scenario that creates a character and assigns it to a scene, verifying both appear in the right-hand story pane.

## Rationale
Extends the established tool-schema-plus-dispatch pattern to characters and their scene
assignments, the next entities in the data model, giving the agent the ability to build a
story's cast and place them in scenes through conversation. Written against the coordinator
as it actually exists after `e005`/`e005a`/`e006` — a `CoordinatorState`-driven Textual TUI
with a live right-hand story pane — rather than the CLI-argument/inline-snapshot design this
encounter was originally drafted against.

## Plan
1. Add a `scene/agent/coordinator/tools/character.py` module with tool schemas and handlers wired to `scene.core.character` and `scene.core.scene_character`, each opening its own `session_scope()`, with `create_character`/`list_characters` resolving `story_id` the same way `e005`'s story tools do, and assignment handlers catching `ValueError` into a tool-result error.
2. Update `scene/cli/coordinator_app.py`'s `CoordinatorApp.__init__` to build and combine the character tool registry with the existing story/scene registries (all built from `self.state`).
3. Update `_render_story_pane` to also render the current story's characters.
4. Update `DEFAULT_SYSTEM_PROMPT` to mention character/cast-assignment capability.
5. Add tests under `test/scene/agent/coordinator/tools/test_character.py` (mirroring `test_story.py`/`test_scene.py`'s structure), and extend `test/scene/cli/test_coordinator_app.py` with a scripted create-and-assign scenario.
6. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-coordinator chat` and ask the agent to add a character and assign it to an existing scene, confirming both actions are reflected in the reply and the right-hand story pane.

## Log
