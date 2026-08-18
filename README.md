# scene-writer

Scene Writer is an agentic, AI-assisted scene-writing tool built around a two-phase generation pipeline:

1. **Scene Construction** — establishes the overall details of a scene (setting, characters, goals, constraints, etc.) before any prose is generated.
2. **Scene Drafting** — incrementally builds the scene's prose, using the construction-phase details together with the output of previously generated scenes for continuity.

Scene definitions and generated output are persisted to a local SQLite database. The project ships as a collection of standalone CLI programs, each driving one agent in the pipeline, with the long-term goal of layering a unified GUI on top of these CLI-driven building blocks.

## Project layout

- `src/scene/cli` — CLI entry points. Some drive an agent; others, like `scene-data`, provide direct CRUD access to data.
- `src/scene/agent` — the two-phase generation pipeline.
- `src/scene/core` — common service layer shared by the CLI and agents for manipulating scene data.
- `src/scene/data` — SQLAlchemy models and SQLite persistence layer.
- `src/scene/gui` — planned unified GUI (not yet implemented).

The SQLite database file lives under a top-level `data/` folder (gitignored; the folder itself is tracked via a placeholder).

## Data model

A story owns a cast of characters, a set of locations, and an ordered sequence of scenes; each
scene may have one or more renderings (generated or edited prose) and can have any number of
characters and locations assigned to it. See [`docs/data-model.md`](docs/data-model.md) for the
full schema, including columns, constraints, and indexes.

## Development

Requires Python 3.13 and [PDM](https://pdm-project.org/).

```
pdm install -G dev
```

Run tests (generates an HTML coverage report at `htmlcov/index.html` by default):

```
pdm run pytest
```

Run linting:

```
pdm run lint
```

Manage persisted data via the `scene-data` CLI:

```
pdm run scene-data --help
```
