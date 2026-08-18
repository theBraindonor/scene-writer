---
archived: false
created_by: John Hoff
created_on: '2026-08-18T14:59:59Z'
name: c003-coordinating-agent
status: open
updated_by: John Hoff
updated_on: '2026-08-18T15:00:02Z'
---

# C003 — Coordinating Agent

## Scope

Implement the coordinating agent: a conversational, LLM-driven agent that can edit a story's
data (story, scene, character, location, and their scene-cast/scene-location assignments) via
tool calls, initially driven through a new interactive CLI REPL. This is the first agent built
in `scene.agent`, and establishes the shared LLM-runtime infrastructure that later
scene-construction and scene-drafting agents will also build on.

Renderings are out of scope for this campaign — the coordinator manages structural story data
only, not generated prose.

## Design decisions

- **LLM access**: the [LiteLLM](https://github.com/BerriAI/litellm) Python SDK
  (`litellm.completion`), called in-process. No LiteLLM *proxy* server — that's a separate
  FastAPI/uvicorn gateway process meant for multi-client deployments, and would complicate a
  future PyInstaller-bundled executable for no benefit to a single-user CLI tool.
- **Model targeting**: fully configurable via environment variables (model name, optional
  `api_base`, optional API key) rather than a hardcoded default, so the same code can target
  OpenRouter (cloud) or a local LM Studio server (OpenAI-compatible local endpoint) by config
  alone.
- **Tool surface**: story, scene, character, and location CRUD, plus `scene_character` and
  `scene_location` assignment tools — mirrors the subset of `scene.core` covering structural
  story data. No rendering tools in this campaign.
- **CLI interaction model**: an interactive REPL scoped to one story
  (`scene-coordinator chat <story_id>`). The conversation lives only for that process's
  lifetime — no persisted chat history/session resume in this campaign.
- **Incremental interactivity**: the CLI lands early (before any entity tools exist) so the
  loop and system prompt can be exercised end-to-end as a "friendly assistant" before tool
  calling is layered in. Once story tools exist, the CLI is revisited to print a live snapshot
  of the story's underlying data after each turn, so data changes made via tool calls are
  immediately visible.

## Log
