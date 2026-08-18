---
archived: false
campaign: c003-coordinating-agent
created_by: John Hoff
created_on: '2026-08-18T15:03:31Z'
depends_on:
- e008-location-tools
kind: scripted
name: e009-readme-coordinator-cli-section
regions:
- cli
status: draft
updated_by: John Hoff
updated_on: '2026-08-18T15:03:53Z'
---

# E009 — README Coordinator CLI Section

## Requirements
- Update `README.md` to document the new `scene-coordinator` CLI and what it does: an interactive, LLM-driven REPL (`scene-coordinator chat <story_id>`) that can view and edit a story's data (story, scenes, characters, locations, and their assignments) via conversation, alongside the existing direct-CRUD `scene-data` CLI.
- Briefly document how the coordinator's LLM connection is configured (the environment variables introduced in `e001-agent-llm-runtime`), including that it can target either a hosted provider (e.g. OpenRouter) or a local OpenAI-compatible server (e.g. LM Studio) by configuration alone, without duplicating the full config reference — keep it brief, consistent with the existing README's light-touch style.
- Do not add integration-style tests or any other test coverage for this change — it is a documentation-only update with no code behavior to verify, consistent with `c002-initial-data-model-and-crud`'s equivalent README encounter.

## Rationale
Closes out the campaign the same way `c002-initial-data-model-and-crud` closed with its own
README encounter: once the coordinator's full tool surface exists, the README should tell a new
contributor it exists, roughly what it does, and how to point it at a model, without duplicating
detail that belongs in code/config.

## Plan
1. In `README.md`, add a brief section (near the existing `scene-data` CLI mention) introducing `scene-coordinator chat <story_id>` and what it can do.
2. Briefly note the `SCENE_AGENT_MODEL`/`SCENE_AGENT_API_BASE`/`SCENE_AGENT_API_KEY` environment variables and that they can target a hosted provider or a local LM Studio-style endpoint.
3. Review the rest of the README for anything now stale (e.g. the "planned unified GUI" framing, if it references only `scene-data`) and adjust wording minimally if needed.

## Verification
- Manually review the rendered `README.md` and confirm the new section reads clearly and accurately reflects the shipped CLI and configuration.
- Run `pdm run lint` and confirm zero errors (no source files are touched, but this keeps the verification step consistent with the rest of the campaign).

## Log
