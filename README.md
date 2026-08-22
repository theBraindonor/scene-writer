# scene-writer

Scene Writer is an agentic, AI-assisted scene-writing tool built around a two-phase generation pipeline:

1. **Scene Construction** — establishes the overall details of a scene (setting, characters, goals, constraints, etc.) before any prose is generated.
2. **Scene Drafting** — incrementally builds the scene's prose, using the construction-phase details together with the output of previously generated scenes for continuity.

Scene definitions and generated output are persisted to a local SQLite database. The project ships as a collection of standalone CLI programs, each driving one agent in the pipeline, alongside a unified `scene-writer` desktop GUI that layers story browsing, direct editing, and chat-driven editing over the same data layer. A separate coordinating agent, driven by its own conversational CLI or the GUI's chat panel, lets a writer build and edit a story's structural data (its scenes, cast, and locations) ahead of generation.

## Project layout

- `src/scene/cli` — CLI entry points. Some drive an agent; others, like `scene-data`, provide direct CRUD access to data.
- `src/scene/agent` — the two-phase generation pipeline.
- `src/scene/core` — common service layer shared by the CLI and agents for manipulating scene data.
- `src/scene/data` — SQLAlchemy models and SQLite persistence layer.
- `src/scene/gui` — the unified desktop GUI (PySide6), launched via the `scene-writer` console script.

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

Generate a story's prose via the `scene-coordinator render` CLI, a separate Textual TUI with a
two-pane layout: a left-hand pane listing the story's scenes with their render status and the
selected scene's full detail, and a right-hand pane showing rendering output:

```
pdm run scene-coordinator render
```

As with `chat`, there's no story id to pass — an in-TUI picker selects the story first. From the
render view, "Render next scene" generates the earliest scene that has no active rendering yet,
in order; "Regenerate this scene" generates a new version of whichever scene is selected, even
if it's already been rendered, activating the new version while leaving prior ones intact. Every
scene keeps its full rendering history: a version list lets you view, activate, or delete any of
the selected scene's past renderings (a scene's only rendering, or its currently active one,
can't be deleted). While a generation is streaming, pressing `Escape` asks for confirmation (Y/N)
before cancelling it; confirming stops the generation and saves whatever prose had been produced
so far.

Use the unified desktop GUI via the `scene-writer` console script, a PySide6 application with
four regions: a story header showing the current story's title with "New Story" and "Open"
buttons — "Open" launches a modal picker listing stories from the database (with a checkbox to
include archived ones) to switch between them; a main entity column, organized into Story,
Characters, Locations, and Scenes tabs, for viewing and editing that story's title, scenario, and
style guidance, its scenes, cast, and locations, and which characters and locations are assigned
to each scene; a rendering column for the selected scene's renderings; and a full-width chat
panel driving the same coordinating agent `scene-coordinator chat` uses:

```
pdm run scene-writer
```

Direct edits made in the entity column and edits made by chatting with the coordinator both go
through the same underlying data layer, so the two ways of working stay consistent with each
other — creating a story from the header and asking the agent to add a scene, for instance, both
show up in the same entity column. The rendering column mirrors `scene-coordinator render`'s
workflow: a version list shows every rendering generated for the selected scene, marking which
one is active; selecting a different version and clicking "Activate Version" makes it active;
"Render" (which regenerates in place once the scene already has an active rendering) streams a
new rendering live and activates it once finished, blocked with a message if an earlier scene in
the story doesn't have an active rendering yet; "Delete Version" removes a version after
confirmation (a scene's only rendering, or its currently active one, can't be deleted); and while
a generation is in progress, "Render" is replaced by "Cancel", which stops it after confirmation
and saves whatever prose had been produced so far as a new version. Checking "Preview Prompt"
before clicking "Render" opens a dialog showing the exact messages that will be sent to the LLM
— useful for verifying multi-scene continuity context is assembled correctly — with "Proceed"
(starts the generation) and "Cancel" (aborts it) buttons. The chat panel reuses the
`SCENE_COORDINATING_AGENT` configuration described below, same as `scene-coordinator chat`; the
rendering column reuses `SCENE_RENDERING_AGENT`, same as `scene-coordinator render`.

Each agent's LLM connection is configured via two gitignored files, each with a
committed `.example` template: `models.yaml` defines named model profiles (a litellm-style
model string, plus an optional `api_base` for a local OpenAI-compatible server such as LM
Studio, and an optional `api_key_env` for a hosted provider such as OpenRouter), and `.env`
selects which profile each agent uses — `SCENE_COORDINATING_AGENT` for `chat`,
`SCENE_RENDERING_AGENT` for `render`. The two agents can be pointed at independently configured
models (for example, a general-purpose model for coordination and a prose- or
role-play-tuned model for rendering). Switching between a hosted provider and a local server is
then just a one-line `.env` edit.
