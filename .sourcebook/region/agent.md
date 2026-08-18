---
created_by: John Hoff
created_on: '2026-08-18T01:47:48Z'
name: agent
path: src/scene/agent
summary: The agentic pipeline itself — the scene-construction phase and the scene-drafting
  phase, plus any shared agent infrastructure.
updated_by: John Hoff
updated_on: '2026-08-18T01:49:40Z'
---

# Agent

Implements the two-phase generation pipeline: (1) scene construction, which establishes overall scene details, and (2) scene drafting, which incrementally builds prose using those details and prior scenes' output. Reads/writes scene and generation state via `scene.data`.
