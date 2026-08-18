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
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T22:06:29Z'
---

# E009 — README Coordinator CLI Section

## Requirements
- Update `README.md` to document the new `scene-coordinator` CLI and what it does: an interactive, LLM-driven Textual TUI (`scene-coordinator chat`) that can view and edit a story's data (story, scenes, characters, locations, and their assignments) via conversation — no story id argument; the agent creates or selects a story conversationally — alongside the existing direct-CRUD `scene-data` CLI. Briefly mention the two-column layout (chat plus a live story-state pane) and the `/quit`/`/clear` commands.
- Briefly document how the coordinator's LLM connection is configured (from `e001-agent-llm-runtime`): a `models.yaml` registry of named model profiles (see `models.example.yaml`), and `.env` role-selector variables (`SCENE_COORDINATING_AGENT`, and `SCENE_RENDERING_AGENT` reserved for a future agent) that each name which registry profile to use — pointing out that this lets the coordinating agent target a hosted provider (e.g. OpenRouter) or a local OpenAI-compatible server (e.g. LM Studio) by editing config alone. Keep it brief, consistent with the existing README's light-touch style, and do not duplicate the full field-by-field reference already in `.env.example`/`models.example.yaml`.
- Do not add integration-style tests or any other test coverage for this change — it is a documentation-only update with no code behavior to verify, consistent with `c002-initial-data-model-and-crud`'s equivalent README encounter.

## Rationale
Closes out the campaign the same way `c002-initial-data-model-and-crud` closed with its own
README encounter: once the coordinator's full tool surface exists, the README should tell a new
contributor it exists, roughly what it does, and how to point it at a model, without duplicating
detail that belongs in code/config. Updated to describe the coordinator as it actually shipped —
a story-id-free Textual TUI (`e005`/`e005a`), not the original CLI-argument REPL this encounter
was drafted against.

## Plan
1. In `README.md`, add a brief section (near the existing `scene-data` CLI mention) introducing `scene-coordinator chat` (no story id) and what it can do, including its two-column TUI layout and `/quit`/`/clear` commands.
2. Briefly describe the two-layer config: `models.yaml` (copy `models.example.yaml`) defines named model profiles, and `.env` (copy `.env.example`) selects which profile each agent role uses via `SCENE_COORDINATING_AGENT`/`SCENE_RENDERING_AGENT`.
3. Review the rest of the README for anything now stale (e.g. the "planned unified GUI" framing, if it references only `scene-data`) and adjust wording minimally if needed.

## Verification
- Manually review the rendered `README.md` and confirm the new section reads clearly and accurately reflects the shipped CLI and configuration.
- Run `pdm run lint` and confirm zero errors (no source files are touched, but this keeps the verification step consistent with the rest of the campaign).

## Log

### Review - 2026-08-18T22:01:37Z - John Hoff

Reviewed e009-readme-coordinator-cli-section against the two applicable lore items (linting, unit-testing). Linting is honored via an explicit pdm run lint verification step despite no source files being touched. Unit-testing is honored via an explicit, justified exemption for documentation-only changes with no code behavior to cover, consistent with the c002-initial-data-model-and-crud README-encounter precedent it cites. Spot-checked README.md (explicitly named in the encounter) and confirmed the Plan's integration point — the existing scene-data CLI subsection under ## Development — and its claim of stale 'planned unified GUI' framing both exist as described, so the Plan is concretely grounded rather than vague. No lore conflicts found; PASS-WITH-NOTES.

### Completed - 2026-08-18T22:06:29Z - John Hoff

Verified: README.md updated with a "Chat with the coordinating agent via the scene-coordinator CLI" subsection under Development (Textual TUI, no story id, chat/story-pane layout, /quit and /clear) plus a paragraph on the models.yaml/.env two-layer LLM config (SCENE_COORDINATING_AGENT, SCENE_RENDERING_AGENT reserved), consistent with the existing scene-data CLI mention's light-touch style. Also lightly updated the intro paragraph to mention the coordinating agent as a separate conversational tool for building structural story data ahead of generation, since that framing was stale (mentioned only the two-phase generation pipeline). pdm run lint reports zero errors; no source files changed, no tests added, per the documentation-only scope. Developer manually reviewed the rendered README diff and confirmed it reads clearly and accurately.
