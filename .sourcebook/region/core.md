---
created_by: John Hoff
created_on: '2026-08-18T03:45:06Z'
name: core
path: src/scene/core
summary: Common underlying service layer providing a shared interface over scene data
  for both the CLI and LLM agent tools.
updated_by: John Hoff
updated_on: '2026-08-18T03:45:06Z'
---

# Core

Common service layer shared by `scene.cli` and `scene.agent`. Provides a unified interface for manipulating scene data, so both the CLI and the LLM-driven agents operate through the same underlying operations rather than each talking to `scene.data` independently.
