# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- Install dependencies: `pdm install -G dev`
- Run all tests: `pdm run pytest` — discovers tests under `test/`, and always writes an HTML coverage report to `htmlcov/index.html` with no extra flags needed.
- Run a single test: `pdm run pytest test/scene/agent/test_init.py::test_package_name`
- Lint: `pdm run lint` (equivalent to `ruff check .`, 120-character line length)

## Architecture

Scene Writer is an agentic scene-writing tool built around a two-phase generation pipeline:

1. **Scene Construction** — establishes the overall details of a scene before any prose is generated.
2. **Scene Drafting** — incrementally builds the scene's prose using the construction-phase details together with the output of previously generated scenes.

Scene definitions and generated output persist to a local SQLite database.

The project is organized into four core packages under `src/scene/`:

- `scene.cli` — standalone CLI programs, each driving one agent in the pipeline. The primary interface until a GUI exists.
- `scene.agent` — the pipeline itself: the construction and drafting phases, plus shared agent infrastructure.
- `scene.data` — the SQLite persistence layer (schema, migrations, data access), consumed by both `scene.cli` and `scene.agent`.
- `scene.gui` — planned unified GUI over the CLI-driven agents. Not yet implemented.

`test/` mirrors `src/`'s package structure without `__init__.py` files (e.g. `src/scene/data/foo.py` → `test/scene/data/test_foo.py`). pytest is configured with `--import-mode=importlib` for this reason — mirrored `__init__.py` files in `test/` would otherwise shadow the real `src/scene` package during collection.

## Project context system (`.sourcebook/`)

This repo's world summary, lore (standards/conventions), regions, and work-tracking (campaigns/encounters) live in `.sourcebook/`, owned exclusively by the `crypts-and-commits` MCP server (or its `cac` CLI fallback) — a Codex hook blocks direct filesystem access to this directory, and equivalent guardrails apply here. Use the `world-manager` and `campaign-manager` skills to read or modify it; never create, edit, or delete files under `.sourcebook/` directly.
