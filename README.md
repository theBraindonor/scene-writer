# scene-writer

Scene Writer is an agentic, AI-assisted scene-writing tool built around a two-phase generation pipeline:

1. **Scene Construction** — establishes the overall details of a scene (setting, characters, goals, constraints, etc.) before any prose is generated.
2. **Scene Drafting** — incrementally builds the scene's prose, using the construction-phase details together with the output of previously generated scenes for continuity.

Scene definitions and generated output are persisted to a local SQLite database. The project ships as a collection of standalone CLI programs, each driving one agent in the pipeline, with the long-term goal of layering a unified GUI on top of these CLI-driven building blocks. A separate coordinating agent, driven by its own conversational CLI, lets a writer build and edit a story's structural data (its scenes, cast, and locations) ahead of generation.

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

Chat with the coordinating agent via the `scene-coordinator` CLI, a Textual TUI with a chat
column on the left and a live-updating story-state pane on the right:

```
pdm run scene-coordinator chat
```

There's no story id to pass — the agent creates or selects a story conversationally, and the
right-hand pane re-renders that story's full data (scenes, cast, locations, and their
assignments) after every turn. `/quit` exits; `/clear` resets the conversation and current
story.

The coordinating agent's LLM connection is configured via two gitignored files, each with a
committed `.example` template: `models.yaml` defines named model profiles (a litellm-style
model string, plus an optional `api_base` for a local OpenAI-compatible server such as LM
Studio, and an optional `api_key_env` for a hosted provider such as OpenRouter), and `.env`
selects which profile the coordinating agent uses via `SCENE_COORDINATING_AGENT`
(`SCENE_RENDERING_AGENT` is reserved for a future rendering agent). Switching between a hosted
provider and a local server is then just a one-line `.env` edit.
