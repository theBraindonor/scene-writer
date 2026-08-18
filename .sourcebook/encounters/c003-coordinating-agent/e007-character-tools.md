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
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T21:44:00Z'
---

# E007 — Character Tools

## Requirements
- Add tool schemas and dispatch handlers for character data, wired to `scene.core.character` (create, get, list, update, delete) and `scene.core.scene_character` (assign/unassign a character to a scene, list characters for a scene / scenes for a character), following the `e004`/`e006` `build_*_tools(state: CoordinatorState)` pattern. `create_character`/`list_characters` take a `story_id`: default it to `state.current_story_id` when omitted, else the same "no current story" error `e005` introduced. `get_character`/`update_character`/`delete_character` operate on an explicit `character_id` (no default, discovered via `list_characters`). `assign_character`/`unassign_character`/`list_characters_for_scene`/`list_scenes_for_character` take explicit `scene_id`/`character_id` arguments; `scene.core.scene_character.assign_character` raises `ValueError` for a missing scene/character or a cross-story pairing — catch it and return a tool-result error, not an unhandled exception.
- Wire the character tool registry into `CoordinatorApp` alongside the existing story and scene tools, using the same `CoordinatorState` instance.
- Extend `_render_story_pane` with two additions: a "Cast of characters" section (name plus a brief description, via `scene.core.character.list_characters`) rendered alongside the existing scenario/style/archived fields; and, within each scene's existing per-scene detail block, a short list of that scene's assigned characters by name (via `scene.core.scene_character.list_characters_for_scene`), so a scene's cast is visible without cross-referencing the top-level cast section.
- Update `DEFAULT_SYSTEM_PROMPT` in `scene/agent/coordinator/loop.py` to describe the coordinator's ability to manage the story's cast of characters and assign them to scenes.
- Cover each tool handler with unit tests (including `story_id` defaulting/no-current-story cases and the `ValueError`-to-tool-error handling for assignment), plus an updated Textual test confirming a scripted scenario that creates a character and assigns it to a scene, verifying the character appears both in the pane's cast section and in that scene's per-scene character list.

## Rationale
Extends the established tool-schema-plus-dispatch pattern to characters and their scene
assignments, the next entities in the data model, giving the agent the ability to build a
story's cast and place them in scenes through conversation. Written against the coordinator
as it actually exists after `e005`/`e005a`/`e006` — a `CoordinatorState`-driven Textual TUI
with a live right-hand story pane that, after `e006`, already renders each scene's full detail
(description, required actions, length) rather than than just position and heading — rather
than the CLI-argument/inline-snapshot design this encounter was originally drafted against.
The two-part pane treatment (a top-level cast section plus each scene's own assigned-character
list) was requested by the developer so a scene's cast is visible in place, without needing to
cross-reference the top-level list by name.

## Plan
1. Add a `scene/agent/coordinator/tools/character.py` module with tool schemas and handlers wired to `scene.core.character` and `scene.core.scene_character`, each opening its own `session_scope()`, with `create_character`/`list_characters` resolving `story_id` the same way `e005`'s story tools do, and assignment handlers catching `ValueError` into a tool-result error.
2. Update `scene/cli/coordinator_app.py`'s `CoordinatorApp.__init__` to build and combine the character tool registry with the existing story/scene registries (all built from `self.state`).
3. Update `_render_story_pane` to add a "Cast of characters" section (via `scene.core.character.list_characters`), and to extend each scene's existing detail block with a line listing that scene's assigned characters by name (via `scene.core.scene_character.list_characters_for_scene`, one call per scene).
4. Update `DEFAULT_SYSTEM_PROMPT` to mention character/cast-assignment capability.
5. Add tests under `test/scene/agent/coordinator/tools/test_character.py` (mirroring `test_story.py`/`test_scene.py`'s structure), and extend `test/scene/cli/test_coordinator_app.py` with a scripted create-and-assign scenario asserting the character shows up in both the cast section and its assigned scene's character list.
6. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-coordinator chat` and ask the agent to add a character and assign it to an existing scene, confirming the character appears in the reply, in the pane's cast-of-characters section, and in that scene's own character list.

## Log

### Review - 2026-08-18T20:57:42Z - John Hoff

Reviewed e007-character-tools against the two world-assigned lore items (linting, unit-testing); both are explicitly honored — Plan step 6 runs `pdm run lint`/`pdm run pytest` with a zero-errors/all-green Verification gate, and Plan step 5 adds `test/scene/agent/coordinator/tools/test_character.py` plus extends `test/scene/cli/test_coordinator_app.py`, correctly mirroring the `src/` layout alongside the existing `test_story.py`/`test_scene.py` precedent. Spot-checked the encounter's factual claims about `scene.core.character` and `scene.core.scene_character` directly and confirmed the CRUD signatures and the `ValueError`-on-missing/cross-story-assignment behavior match the Plan exactly. No lore conflicts found and no unverifiable concerns to flag. PASS-WITH-NOTES.

### Message - 2026-08-18T21:07:39Z - John Hoff

Deviation from the reviewed Plan, per developer feedback after the first manual pass at the right-hand pane: the "Cast of characters" section originally showed only name and description on one line. The developer asked for each character's motive to be included too, so it was expanded to a name line followed by indented "Description:" and "Motive:" lines, matching the per-scene detail block's style. Updated the scripted round-trip test in test/scene/cli/test_coordinator_app.py to assert the description and motive lines appear. pdm run pytest (235/235, 100% coverage) and pdm run lint (zero errors) both pass after the change.

### Completed - 2026-08-18T21:44:00Z - John Hoff

Verified: pdm run pytest passes 235/235 with 100% coverage, pdm run lint zero errors. Delivered scene/agent/coordinator/tools/character.py (build_character_tools: create/get/list/update/delete_character plus assign_character/unassign_character/list_characters_for_scene/list_scenes_for_character, story_id defaulting to current story for create_character/list_characters, ValueError-to-tool-error handling for missing scene/character and cross-story assignment, clear errors for missing character_id/scene_id); CoordinatorApp now combines story, scene, and character tool registries off the same CoordinatorState; DEFAULT_SYSTEM_PROMPT updated to mention cast/assignment capability. Developer manually verified against the live LM Studio server via scene-coordinator chat, confirming character creation and scene assignment appear in the agent's reply and the right-hand pane. Per developer feedback during manual verification, the pane's "Cast of characters" section was expanded beyond the Plan's name+brief-description to also show each character's motive (Description/Motive lines matching the per-scene detail style) — recorded as a deviation message and covered by an updated scripted round-trip test.
