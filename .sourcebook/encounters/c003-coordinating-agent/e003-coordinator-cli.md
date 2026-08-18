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
status: draft
updated_by: John Hoff
updated_on: '2026-08-18T15:03:50Z'
---

# E003 — Coordinator CLI

## Requirements
- Add a new Typer-based CLI program, `scene-coordinator`, registered as a project console script (`[project.scripts]` in `pyproject.toml`), in a new `scene/cli/coordinator.py` module.
- Add a `chat <story_id>` command that: looks up the story via `scene.core.story.get_story`, exiting with a not-found message (matching the `scene-data` CLI's existing not-found pattern) if it doesn't exist; then opens an interactive REPL reading lines from stdin and printing the assistant's replies, using the tool loop from `e002-coordinator-tool-loop` with its default friendly-assistant system prompt and an empty tool registry (no entity tools wired in yet).
- Support a clear way to exit the REPL (e.g. an `exit`/`quit` input, or EOF/Ctrl-D), without raising an unhandled exception.
- Cover the command with tests using Typer's `CliRunner` (supplying scripted `input=`), mocking `scene.agent.llm.complete` so no real network call is made, covering: story-not-found exits non-zero with a message; a basic conversation turn prints the mocked assistant reply; the exit command ends the REPL cleanly.

## Rationale
Landing the CLI before any entity tools exist (per explicit developer direction) proves the full
plumbing between `scene.cli`, `scene.core.story`, and the `e002` coordinator loop end-to-end, and
lets the developer start talking to the agent immediately rather than waiting for the full tool
surface to be built out.

## Plan
1. Create `scene/cli/coordinator.py` with a Typer `app` and a `chat` command taking `story_id: int`.
2. Resolve the story via `scene.core.story.get_story` inside a `session_scope()`; on `None`, echo a not-found message and `raise typer.Exit(code=1)`, matching `scene/cli/data.py`'s existing pattern.
3. Implement the REPL loop: read a line via `typer.prompt`/`input`, break cleanly on an exit sentinel or `EOFError`/`KeyboardInterrupt`, otherwise call the `e002` loop's turn function with the running history, the default system prompt, and an empty tool registry, and print the returned reply.
4. Register `scene-coordinator = "scene.cli.coordinator:app"` under `[project.scripts]` in `pyproject.toml`.
5. Add tests under `test/scene/cli/test_coordinator.py` using `typer.testing.CliRunner`, mocking `scene.agent.llm.complete`, covering the scenarios in Requirements.
6. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-coordinator chat <story_id>` against a story created via `scene-data story create`, pointed at a configured local LM Studio model, and confirm a conversational reply comes back and the REPL exits cleanly on the exit command.

## Log
