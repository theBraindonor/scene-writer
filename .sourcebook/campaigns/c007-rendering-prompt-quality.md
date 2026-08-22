---
archived: false
created_by: John Hoff
created_on: '2026-08-22T04:50:44Z'
name: c007-rendering-prompt-quality
status: draft
updated_by: John Hoff
updated_on: '2026-08-22T04:50:44Z'
---

# C007 — Rendering Prompt Quality

## Scope

Iterative refinement of the scene-rendering agent's system prompt (`build_render_messages` in
`src/scene/agent/rendering.py`), driven by the developer's own hands-on testing of generated
prose quality against locally-configured models. Kept as its own campaign rather than folded
into `c006-gui-usability` because it changes `scene.agent`, which `c006` explicitly excludes
("no changes to `scene.core`/`scene.data`/`scene.agent`... not on adding new raw story-domain
functionality").

Out of scope: any GUI, CLI, or TUI surface change (`c006` and the existing TUI/CLI already cover
those) and any change to the rendering pipeline's mechanics (message assembly order, streaming,
persistence) — this campaign is specifically about the *content* of the instructions given to
the LLM, not how the pipeline invokes it.

## Log
