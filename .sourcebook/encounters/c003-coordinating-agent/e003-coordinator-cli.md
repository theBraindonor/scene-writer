---
archived: false
campaign: c003-coordinating-agent
created_by: John Hoff
created_on: '2026-08-18T15:02:55Z'
depends_on:
- e002-coordinator-tool-loop
kind: scripted
name: e003-coordinator-cli
regions:
- agent
- cli
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T17:15:55Z'
---

# E003 — Coordinator CLI

## Requirements
- Add a new Typer-based CLI program, `scene-coordinator`, registered as a project console script (`[project.scripts]` in `pyproject.toml`), in a new `scene/cli/coordinator.py` module.
- Add a `chat <story_id>` command that: looks up the story via `scene.core.story.get_story`, exiting with a not-found message (matching the `scene-data` CLI's existing not-found pattern) if it doesn't exist; resolves the coordinating agent's LLM config once via `scene.agent.config.get_llm_config(AgentRole.COORDINATING)` from `e001-agent-llm-runtime`, surfacing that resolution's errors (unset `SCENE_COORDINATING_AGENT`, unknown profile, malformed `models.yaml`) as a clear CLI error rather than a raw traceback; then opens an interactive REPL reading lines from stdin and printing the assistant's replies, using the tool loop from `e002-coordinator-tool-loop` with the resolved config, its default friendly-assistant system prompt, and an empty tool registry (no entity tools wired in yet).
- Support a clear way to exit the REPL (e.g. an `exit`/`quit` input, or EOF/Ctrl-D), without raising an unhandled exception.
- Cover the command with tests using Typer's `CliRunner` (supplying scripted `input=`), mocking `scene.agent.llm.complete` and `scene.agent.config.get_llm_config` so no real network call, `.env`, or `models.yaml` file is touched, covering: story-not-found exits non-zero with a message; a basic conversation turn prints the mocked assistant reply; the exit command ends the REPL cleanly; a config-resolution failure (e.g. `get_llm_config` raising) exits with a clear message rather than a traceback.

## Rationale
Landing the CLI before any entity tools exist (per explicit developer direction) proves the full
plumbing between `scene.cli`, `scene.core.story`, `e001`'s config resolution, and the `e002`
coordinator loop end-to-end, and lets the developer start talking to the agent immediately rather
than waiting for the full tool surface to be built out.

## Plan
1. Create `scene/cli/coordinator.py` with a Typer `app` and a `chat` command taking `story_id: int`.
2. Resolve the story via `scene.core.story.get_story` inside a `session_scope()`; on `None`, echo a not-found message and `raise typer.Exit(code=1)`, matching `scene/cli/data.py`'s existing pattern.
3. Resolve the coordinating agent's config via `get_llm_config(AgentRole.COORDINATING)`, catching and re-echoing any raised error as a clear CLI message plus `typer.Exit(code=1)`, before entering the REPL.
4. Implement the REPL loop: read a line via `typer.prompt`/`input`, break cleanly on an exit sentinel or `EOFError`/`KeyboardInterrupt`, otherwise call the `e002` loop's turn function with the resolved config, the running history, the default system prompt, and an empty tool registry, and print the returned reply.
5. Register `scene-coordinator = "scene.cli.coordinator:app"` under `[project.scripts]` in `pyproject.toml`.
6. Add tests under `test/scene/cli/test_coordinator.py` using `typer.testing.CliRunner`, mocking `scene.agent.llm.complete` and `scene.agent.config.get_llm_config`, covering the scenarios in Requirements.
7. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-coordinator chat <story_id>` against a story created via `scene-data story create`, with a real profile filled into `models.yaml` and `SCENE_COORDINATING_AGENT` set in `.env` pointing at a running LM Studio server, and confirm a conversational reply comes back and the REPL exits cleanly on the exit command.

## Log

### Review - 2026-08-18T16:21:12Z - John Hoff

Reviewed e003-coordinator-cli against the two applicable world-assigned lore items (linting, unit-testing) and against e001/e002's actual shipped interfaces. Both lore items are explicitly and correctly addressed: Plan step 7 and Verification require `pdm run lint` with zero errors, and Plan step 6/Verification add `test/scene/cli/test_coordinator.py` (correctly mirroring the planned `src/scene/cli/coordinator.py`) with `pdm run pytest` required green. The Plan's assumptions about e001/e002 are accurate on `get_llm_config(AgentRole.COORDINATING)`, `LLMConfig`, `AgentRole`, `get_story`, and the `scene-data` not-found/`pyproject.toml` console-script patterns, all confirmed against the real source. Two minor notes for the implementer, not lore conflicts: (1) Plan step 4's restatement of the `run_turn` call omits the `user_message` argument that the real signature requires alongside `history`, though the Requirements' REPL description makes the intent clear; (2) `load_registry`'s malformed-structure case raises `TypeError` rather than `RuntimeError` (a deliberate e001 deviation), so the config-resolution error handling in Plan step 3 should explicitly catch both types rather than narrowing to `RuntimeError`, or the "malformed models.yaml" Requirement won't actually be satisfied. No lore conflicts found; PASS-WITH-NOTES.

### Completed - 2026-08-18T17:15:55Z - John Hoff

Verified: pdm run pytest passes 152/152 with 100% coverage, including the new src/scene/cli/coordinator.py (scene-coordinator chat <story_id>) and its tests under test/scene/cli/test_coordinator.py, covering story-not-found, a basic conversation turn, the exit command, an immediate-EOF case, and a config-resolution failure surfaced cleanly. pdm run lint reports zero errors. Registered scene-coordinator = "scene.cli.coordinator:app" in pyproject.toml. Manually ran `pdm run scene-coordinator chat <story_id>` against a real story and a live local LM Studio server and got a genuine conversational reply, with the REPL exiting cleanly (exit_code 0) on 'exit'.

Two deviations from Plan, both required to make the CLI actually usable: (1) Typer collapses a Typer() app with exactly one registered command into a bare root command, which would have silently dropped the `chat` subcommand name the Requirements specify (`scene-coordinator <story_id>` instead of `scene-coordinator chat <story_id>`) — fixed by adding an explicit @app.callback(), keeping `chat` addressable and leaving room for future subcommands. (2) Manual verification surfaced a real bug in e001's already-completed src/scene/agent/llm.py: litellm's OpenAI-compatible client raises `OpenAIError: Missing credentials` when no api_key is passed at all, even for a local LM Studio server that doesn't validate one — e001's mocked tests couldn't catch this since it only reproduces on a real network call. Fixed llm.py so that when api_base is set and no api_key is configured, complete() now passes a "not-needed" placeholder; added test/scene/agent/test_llm.py coverage for both the api_base-without-key and api_key-without-api_base branches. e001's encounter body is completed/locked so this fix is recorded here instead.
