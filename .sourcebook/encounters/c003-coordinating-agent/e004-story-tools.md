---
archived: false
campaign: c003-coordinating-agent
created_by: John Hoff
created_on: '2026-08-18T15:03:03Z'
depends_on:
- e003-coordinator-cli
kind: scripted
name: e004-story-tools
regions:
- agent
- cli
status: draft
updated_by: John Hoff
updated_on: '2026-08-18T15:03:51Z'
---

# E004 — Story Tools

## Requirements
- Add tool schemas and dispatch handlers for story data, wired to `scene.core.story`: create, get, list, update, archive, and unarchive.
- Each tool handler must open its own `session_scope()` (matching the existing `scene-data` CLI's per-operation session pattern, appropriate for a long-running REPL process) and return a JSON-serializable result describing the story (or a structured not-found/error result) suitable for feeding back to the model as a tool result.
- Wire this tool registry into `scene-coordinator chat`'s coordinator loop (from `e003-coordinator-cli`), replacing the empty registry, scoped to the story the REPL was started against — the `create_story`/`list_stories` tools operate globally, but tools that mutate/read a single story (`get`, `update`, `archive`, `unarchive`) should default to the REPL's story when no id is given, since the agent is working within one story's context.
- Update the default system prompt (from `e002-coordinator-tool-loop`) to describe the coordinator's real ability to view and edit the story's title, scenario, and style guidance, replacing the placeholder "friendly assistant, no capabilities yet" language.
- Cover each tool handler with unit tests verifying it calls the correct `scene.core.story` function and shapes its result correctly, plus an updated CLI test confirming a scripted tool-call round trip actually persists a change to the story (verified by reading it back via `scene.core.story.get_story`).

## Rationale
This is the first entity wired into the coordinator, establishing the tool-schema-plus-dispatch
pattern that `e006-scene-tools`, `e007-character-tools`, and `e008-location-tools` will each
repeat for their own entity, and gives the agent real editing power over story data via
conversation for the first time.

## Plan
1. Add a `scene/agent/coordinator/tools/story.py` module exposing a list of tool schemas (OpenAI/LiteLLM tool-calling JSON-schema format) and a name-to-handler mapping, with handlers calling `scene.core.story` functions inside their own `session_scope()`.
2. Update `scene/cli/coordinator.py`'s `chat` command to build its tool registry from this module and pass the REPL's `story_id` as the default target for single-story tools.
3. Update the default system prompt to mention the coordinator's story-editing capability.
4. Add tests under `test/scene/agent/coordinator/tools/test_story.py` (mirroring the module's location) for each handler, and extend `test/scene/cli/test_coordinator.py` with a scripted tool-call scenario that mutates the story and confirms persistence.
5. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `scene-coordinator chat <story_id>` and ask the agent to update the story's scenario, then confirm the change with `scene-data story get <story_id>`.

## Log
