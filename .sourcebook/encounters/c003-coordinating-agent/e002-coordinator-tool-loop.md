---
archived: false
campaign: c003-coordinating-agent
created_by: John Hoff
created_on: '2026-08-18T15:02:47Z'
depends_on:
- e001-agent-llm-runtime
kind: scripted
name: e002-coordinator-tool-loop
regions:
- agent
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T16:15:27Z'
---

# E002 — Coordinator Tool Loop

## Requirements
- Add an entity-agnostic, in-memory conversation engine in `scene.agent` that drives a tool-calling loop against the `complete()` wrapper from `e001-agent-llm-runtime`: given a resolved LLM config (an `e001` config object, opaque to this module), message history, a system prompt, and a tool registry (mapping tool name to its schema and a handler callable), it repeatedly calls `complete(config, messages, tools)` — executing any requested tool calls via the registry and feeding their results back as tool-role messages — until the model returns a plain text reply, which is then returned to the caller. This module must not itself resolve config (no `AgentRole`, no `.env`, no registry lookups) — the caller resolves and passes it in.
- The tool registry must support being empty (no tools supplied) so the loop is independently testable and usable by the CLI before any entity tools exist.
- Include a basic default "friendly assistant" system prompt describing the coordinator only in general terms (a helpful assistant for developing a story), explicitly not yet describing tool-calling capabilities — this will be revised once real tools exist.
- Cover the loop with unit tests, mocking `scene.agent.llm.complete`, covering at minimum: a plain conversation turn with no tool calls; a single tool-call round trip where the handler is invoked and its result is fed back before a final reply; multiple sequential tool calls in one turn; and an unknown/unregistered tool name being reported back to the model as a tool error rather than raising. Tests pass a stub/fake config object — they must not depend on `e001`'s real config resolution, `.env`, or `models.yaml`.

## Rationale
Separating the tool-calling loop's mechanics from any specific entity's tools lets it be built,
tested, and exercised through the CLI (`e003-coordinator-cli`) before the story/scene/character/
location tool encounters exist, and gives every later entity-tools encounter (`e004`, `e006`,
`e007`, `e008`) a stable, already-tested engine to plug tool registries into. Taking an
already-resolved config as a plain argument (rather than resolving it itself) keeps this module
ignorant of `AgentRole`/`.env`/the model registry from `e001`, so it has no idea which agent role
it's serving — that's the caller's concern.

## Plan
1. In `scene.agent`, add a `coordinator` subpackage (e.g. `scene/agent/coordinator/__init__.py`) with a small `Tool` representation (name, JSON-schema tool definition, handler callable) and a loop function/class (e.g. `run_turn(config, history, user_message, tools, system_prompt)`) that appends the user message, calls `complete(config, messages, tools=...)` with the tool registry's schemas, dispatches any `tool_calls` in the response to the matching handler, appends the handler's result as a tool-role message, and repeats until a plain assistant reply is returned.
2. Handle an unregistered tool name by feeding a tool-role error result back to the model (not raising), so the model can recover conversationally.
3. Add a default system prompt constant describing a friendly, general-purpose assistant for story development, with no mention of specific tool capabilities yet.
4. Add unit tests under `test/scene/agent/test_coordinator.py` (or `test/scene/agent/coordinator/test_loop.py`, mirroring the module's location) mocking `scene.agent.llm.complete` to return scripted responses for each scenario in the Requirements, passing a stub config object rather than resolving a real one.
5. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually trace through one scripted mocked scenario (a tool call followed by a final reply) to confirm the message history sent to `complete()` on the second call includes the tool result in the shape the OpenAI/LiteLLM tool-calling protocol expects.

## Log

### Review - 2026-08-18T16:09:41Z - John Hoff

Reviewed e002-coordinator-tool-loop against the two applicable world-assigned lore items (linting, unit-testing) and against e001's actual shipped interfaces. Both lore items are explicitly and correctly addressed: Plan step 5 and Verification require `pdm run lint` with zero errors, and Plan step 4/Verification require new tests under `test/scene/agent/...` (mirroring the eventual source module location) with `pdm run pytest` green, covering all four scenarios called out in Requirements. The Plan's assumptions about e001 are accurate: `complete(config, messages, tools=None)` in `scene.agent.llm`, the frozen `LLMConfig` dataclass, and `AgentRole` are all described and used consistently with the real source in `src/scene/agent/{llm,config,role,registry}.py`, and the module correctly avoids resolving `AgentRole`/`.env`/the registry itself, leaving that to the caller. One minor open point, not a defect: the exact test file path (`test/scene/agent/test_coordinator.py` vs. a nested `coordinator/test_loop.py`) is left pending the final source layout, though the Plan explicitly commits to mirroring whichever layout is chosen, satisfying the lore's actual rule. No lore conflicts found; PASS-WITH-NOTES.

### Completed - 2026-08-18T16:15:27Z - John Hoff

Verified: pdm run pytest passes 145/145 with 100% coverage, including the new src/scene/agent/coordinator/loop.py (Tool dataclass, run_turn, DEFAULT_SYSTEM_PROMPT) and its tests under test/scene/agent/coordinator/test_loop.py, covering a plain turn, a single tool-call round trip, multiple sequential tool calls in one turn, and an unknown-tool error fed back as a tool result rather than raised. pdm run lint reports zero errors. Manually traced a scripted tool-call round trip and confirmed the second complete() call's outgoing messages include system, user, the assistant message with tool_calls, and the tool-role result message in the exact OpenAI/LiteLLM tool-calling shape. Implemented as src/scene/agent/coordinator/loop.py (not a __init__.py-only module) to leave room for the coordinator package's planned tools/ subpackage in later encounters.
