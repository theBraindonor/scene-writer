---
archived: false
created_by: John Hoff
created_on: '2026-08-18T14:59:59Z'
name: c003-coordinating-agent
status: open
updated_by: John Hoff
updated_on: '2026-08-18T17:57:04Z'
---

# C003 — Coordinating Agent

## Scope

Implement the coordinating agent: a conversational, LLM-driven agent that can edit a story's
data (story, scene, character, location, and their scene-cast/scene-location assignments) via
tool calls, driven through a new interactive CLI. This is the first agent built in
`scene.agent`, and establishes the shared LLM-runtime infrastructure that later
scene-construction and scene-drafting (rendering) agents will also build on.

Renderings are out of scope for this campaign — the coordinator manages structural story data
only, not generated prose.

## Design decisions

- **LLM access**: the [LiteLLM](https://github.com/BerriAI/litellm) Python SDK
  (`litellm.completion`), called in-process. No LiteLLM *proxy* server — that's a separate
  FastAPI/uvicorn gateway process meant for multi-client deployments, and would complicate a
  future PyInstaller-bundled executable for no benefit to a single-user CLI tool.
- **Model targeting — a named model registry, not flat config**: the coordinating agent and the
  future rendering agent are highly likely to run on two different models (an "instruct" model
  suits tool-calling coordination; a "role-play" model suits prose rendering), and the developer
  wants to swap either independently via config, with a seam that a later GUI can also flip
  live. So model configuration is two-layered:
  - A **model registry** (`models.yaml`, gitignored personal file; `models.example.yaml`
    committed as a template) defines named profiles, each with a litellm-style `model` string,
    an optional `api_base` (for a local OpenAI-compatible server such as LM Studio), and an
    optional `api_key_env` naming the `.env` variable holding that profile's API key.
  - Two **role-selector environment variables**, `SCENE_COORDINATING_AGENT` and
    `SCENE_RENDERING_AGENT`, each naming which registry profile that role currently uses.
    `SCENE_RENDERING_AGENT` is defined now (for consistency and to reserve the seam) even
    though no rendering agent consumes it yet in this campaign.
  - `.env` (gitignored, `python-dotenv`-loaded, `.env.example` committed as a template) holds
    the role selectors and the actual API key values the registry's `api_key_env` fields
    reference — secrets never live in `models.yaml`.
  - This lets OpenRouter (cloud) and a local LM Studio server be defined as two profiles and
    swapped per role by changing one `.env` line, with no code change either way.
- **Tool surface**: story, scene, character, and location CRUD, plus `scene_character` and
  `scene_location` assignment tools — mirrors the subset of `scene.core` covering structural
  story data. No rendering tools in this campaign.
- **CLI interaction model — a two-pane TUI, no required story id**: the CLI first landed
  (`e003-coordinator-cli`) as a plain-text REPL scoped to a story id passed on the command line
  (`scene-coordinator chat <story_id>`), with each entity-tools encounter defaulting its
  single-story tools to that fixed id. Once story tools existed and the agent could list/create
  stories itself via tool calls, a fixed CLI-supplied story id stopped pulling its weight — so
  the interaction model pivoted (from `e005-coordinator-cli-state-display` onward) to a
  [Textual](https://textual.textualize.io/) TUI with two columns: a left-hand chat pane, and a
  right-hand pane that re-renders the current story's data straight from `scene.core` after
  every turn, so edits made via tool calls are visible immediately without a separate lookup.
  `scene-coordinator chat` now takes no story id at all — the "current story" becomes mutable
  session state (starts unset; set/switched whenever the agent successfully creates or fetches
  a story by id), which single-story tools default to when the model omits an explicit id, and
  which the right-hand pane renders. `/quit` exits the app; `/clear` resets both the chat
  history and the current-story reference to a genuinely blank session. The conversation still
  lives only for the process's lifetime — no persisted chat history/session resume in this
  campaign.
- **Incremental interactivity**: the CLI landed early (before any entity tools existed) so the
  loop and system prompt could be exercised end-to-end as a "friendly assistant" before tool
  calling was layered in, then was revisited once story tools existed to add the live TUI state
  display described above.

## Log
