---
archived: false
campaign: c003-coordinating-agent
created_by: John Hoff
created_on: '2026-08-18T15:03:15Z'
depends_on:
- e005a-coordinator-tui-streaming
kind: scripted
name: e006-scene-tools
regions:
- agent
- cli
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T20:22:39Z'
---

# E006 — Scene Tools

## Requirements
- Add tool schemas and dispatch handlers for scene data, wired to `scene.core.scene`: create, get, list, update, and delete — following the pattern established in `e004-story-tools`/`e005-coordinator-cli-state-display` (own `session_scope()` per handler, JSON-serializable results, a `build_scene_tools(state: CoordinatorState)` factory mirroring `build_story_tools`). `create_scene`/`list_scenes` take a `story_id` (the underlying `scene.core.scene` functions require one): default it to `state.current_story_id` when the model omits it, returning the same "no current story" error `e005` introduced when neither is available. `get_scene`/`update_scene`/`delete_scene` operate on a `scene_id` the underlying functions require explicitly — there is no story-level default for a scene id, so the model must supply one (typically discovered via `list_scenes`).
- Wire the scene tool registry into `CoordinatorApp` alongside the story tools from `e004`/`e005`, using the same `CoordinatorState` instance so both tool sets see the same current story.
- Extend `CoordinatorApp`'s right-hand story pane (`_render_story_pane`) to also list the current story's scenes (position and heading, briefly) beneath its existing fields, re-rendered fresh from `scene.core.scene.list_scenes` alongside the story lookup already happening there — continuing the pane's original purpose of reflecting the current story's data as tool calls update it, per this campaign's design decisions.
- Update `DEFAULT_SYSTEM_PROMPT` in `scene/agent/coordinator/loop.py` to describe the coordinator's ability to view and edit the story's scenes (heading, description, required actions, length, position), in addition to story-level fields.
- Cover each tool handler with unit tests verifying it calls the correct `scene.core.scene` function and shapes its result correctly (including the `story_id` defaulting/no-current-story cases for `create_scene`/`list_scenes`), plus an updated Textual test (`test/scene/cli/test_coordinator_app.py`) confirming a scripted tool-call round trip creates a scene and that it appears in the right-hand story pane.

## Rationale
Extends the tool-schema-plus-dispatch pattern from `e004-story-tools` to scenes, the next entity
in the data model, giving the agent the ability to build up a story's ordered scene list through
conversation. Written against the coordinator as it actually exists after `e005`/`e005a` — a
`CoordinatorState`-driven Textual TUI with no CLI-supplied story id and a live right-hand pane —
rather than the CLI-argument/inline-snapshot design this encounter was originally drafted against
before those two encounters landed.

## Plan
1. Add a `scene/agent/coordinator/tools/scene.py` module with tool schemas and handlers wired to `scene.core.scene`, each opening its own `session_scope()`; `create_scene`/`list_scenes` resolve `story_id` the same way `e005`'s story tools resolve their target (explicit argument, else `state.current_story_id`, else a clear error).
2. Update `scene/cli/coordinator_app.py`'s `CoordinatorApp.__init__` to build and combine the scene tool registry with the story tool registry (both built from the same `self.state`).
3. Update `_render_story_pane` to also render the current story's scenes (position + heading) via `scene.core.scene.list_scenes`.
4. Update `DEFAULT_SYSTEM_PROMPT` in `scene/agent/coordinator/loop.py` to mention scene-editing capability.
5. Add tests under `test/scene/agent/coordinator/tools/test_scene.py` (mirroring `test_story.py`'s structure), and extend `test/scene/cli/test_coordinator_app.py` with a scripted scene-creation scenario, asserting the resulting story pane includes the new scene.
6. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-coordinator chat` and ask the agent to add a scene to the current story, confirming it appears both in the agent's reply and in the right-hand story pane.

## Log

### Review - 2026-08-18T19:53:57Z - John Hoff

Reviewed e006-scene-tools (scripted) against the two lore items applicable via world assignment: linting and unit-testing. Both are explicitly honored — the Plan's final step runs `pdm run lint` and `pdm run pytest` and requires fixing any failures, and the Verification section restates zero-lint-errors and all-tests-green as exit criteria. Unit test coverage is planned per-handler (including story_id defaulting/no-current-story edge cases for create_scene/list_scenes) under `test/scene/agent/coordinator/tools/test_scene.py` and an extended `test/scene/cli/test_coordinator_app.py`, correctly mirroring the src/ → test/ path convention required by the unit-testing lore. Referenced source and test paths (coordinator/tools/story.py, coordinator_app.py, loop.py, core/scene.py, and their test counterparts) were confirmed to exist, so the plan is grounded in the actual codebase state post-e005/e005a rather than a stale design. No conflicts or gaps found against applicable lore; no unverifiable concerns to flag.

### Message - 2026-08-18T20:12:27Z - John Hoff

Deviation from the reviewed Plan, per developer feedback after the first manual pass at the right-hand pane: the scene listing in `_render_story_pane` originally showed only position and heading (as the Plan's step 3 specified). The developer asked to see full scene details instead, so it was expanded to also show each scene's description, required actions, and length beneath its heading line. Updated the scripted round-trip test in `test/scene/cli/test_coordinator_app.py` to assert these fields appear in the pane. pdm run pytest (206/206, 100% coverage) and pdm run lint (zero errors) both pass after the change.

### Completed - 2026-08-18T20:22:39Z - John Hoff

Verified: pdm run pytest passes 206/206 with 100% coverage, pdm run lint zero errors. Delivered scene/agent/coordinator/tools/scene.py (build_scene_tools: create/get/list/update/delete_scene, story_id defaulting to current story for create_scene/list_scenes, clear errors for missing scene_id and no-current-story); CoordinatorApp now combines story and scene tool registries off the same CoordinatorState; DEFAULT_SYSTEM_PROMPT updated to mention scene editing. Developer manually verified against the live LM Studio server via scene-coordinator chat, confirming scene creation appears both in the agent's reply and the right-hand pane. Per developer feedback during manual verification, _render_story_pane's scene listing was expanded beyond the Plan's position+heading to show each scene's full detail (description, required actions, length) — recorded as a deviation message and covered by an updated scripted round-trip test.
