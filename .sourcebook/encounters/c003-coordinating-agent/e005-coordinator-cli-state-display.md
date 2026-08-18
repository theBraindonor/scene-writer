---
archived: false
campaign: c003-coordinating-agent
created_by: John Hoff
created_on: '2026-08-18T15:03:10Z'
depends_on:
- e004-story-tools
kind: scripted
name: e005-coordinator-cli-state-display
regions:
- cli
status: draft
updated_by: John Hoff
updated_on: '2026-08-18T15:03:52Z'
---

# E005 — Coordinator CLI State Display

## Requirements
- After each REPL turn in `scene-coordinator chat` (i.e. once the assistant's reply has been printed), print a snapshot of the story's current full state, queried fresh from `scene.core`: the story's own fields, its scenes (in position order), its characters, its locations, and the scene-character/scene-location assignments — so changes made via tool calls are visible immediately, without a separate `scene-data` lookup.
- Factor the snapshot rendering into a reusable, independently testable function (e.g. a `render_story_snapshot(session, story_id) -> str` helper in `scene/cli/coordinator.py` or a small sibling module), so later encounters that add more entity tools (`e006`, `e007`, `e008`) don't need to touch the CLI again to have their data show up.
- Render empty collections gracefully (e.g. "No scenes yet.") rather than omitting sections or erroring, since at this point in the campaign only story tools exist and scenes/characters/locations will typically still be empty.

## Rationale
Requested by the developer to see the underlying data model update live in the REPL as the agent
edits it via tool calls, rather than needing to shell out to `scene-data` after each turn. Built
generically against `scene.core` now so it naturally starts showing scenes/characters/locations
once `e006`–`e008` add the tools that can populate them, without further CLI changes.

## Plan
1. Add a snapshot-rendering helper that, given a session and `story_id`, calls `scene.core.story.get_story`, `scene.core.scene.list_scenes`, `scene.core.character.list_characters`, `scene.core.location.list_locations`, and the relevant `scene_character`/`scene_location` listing functions, formatting the result as readable text.
2. Call this helper from `scene/cli/coordinator.py`'s `chat` REPL loop after each turn's reply is printed, opening its own `session_scope()`.
3. Add tests that seed a story with scenes/characters/locations directly via `scene.core` and assert the rendered snapshot reflects them, plus a case with no related data to confirm the empty-state rendering.
4. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `scene-coordinator chat <story_id>`, ask the agent to change the story's scenario, and confirm the printed snapshot reflects the change immediately after the reply.

## Log
