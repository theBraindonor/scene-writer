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
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T17:46:34Z'
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

### Review - 2026-08-18T17:22:57Z - John Hoff

Reviewed e004-story-tools against the two applicable world-assigned lore items (linting, unit-testing) — both regions (agent, cli) carry no additional region-specific lore. Both items are explicitly and correctly addressed: Plan step 5/Verification require `pdm run lint` with zero errors, and Plan step 4/Verification add `test/scene/agent/coordinator/tools/test_story.py` (correctly mirroring the planned source module) plus extend the existing `test/scene/cli/test_coordinator.py`, with `pdm run pytest` required green. The Plan's assumptions about e001-e003's real interfaces are accurate: `run_turn`'s signature, the `chat(story_id)` command's shape and available `story_id` local, `session_scope()`'s no-required-args form, and all six `scene.core.story` function signatures (including that only `create_story`/`list_stories` omit a `story_id`) match the real source exactly. One minor gap for the implementer, not a lore conflict: Plan step 1 describes the new tools module as exposing a schemas list plus a separate name-to-handler mapping, but `run_turn` actually consumes `Sequence[Tool]` (a combined name+schema+handler dataclass from e002), and the Plan never states how these get assembled into `Tool` instances before being passed into the `chat` command's `run_turn` call. Separately flagged but unverifiable within this review's bounded surface: the Requirements' claim that handlers should match "the existing scene-data CLI's per-operation session pattern" references scene/cli/data.py, which was not part of the cited reading surface. No lore conflicts found; PASS-WITH-NOTES.

### Completed - 2026-08-18T17:46:34Z - John Hoff

Verified: pdm run pytest passes 165/165 with 100% coverage, including the new src/scene/agent/coordinator/tools/story.py (build_story_tools returning Sequence[Tool] directly, per the review's note about run_turn's real signature) and its tests under test/scene/agent/coordinator/tools/test_story.py, covering all six tools including not-found and default-vs-explicit story_id cases. test/scene/cli/test_coordinator.py extended with a scripted tool-call round trip confirming a real update_story call persists via get_story. pdm run lint reports zero errors. Manually ran scene-coordinator chat against a real story and the live LM Studio server, asked it to update the scenario, and confirmed via scene-data story get that the change persisted. DEFAULT_SYSTEM_PROMPT in scene/agent/coordinator/loop.py updated to describe the coordinator's real story-editing capability, replacing the e002 placeholder text.
