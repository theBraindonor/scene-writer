---
created_by: John Hoff
created_on: '2026-08-18T03:45:06Z'
name: core
path: src/scene/core
summary: Common service layer shared by scene.cli and scene.agent, organized as one
  module per entity exposing CRUD functions over a caller-supplied SQLAlchemy Session.
updated_by: John Hoff
updated_on: '2026-08-18T04:27:09Z'
---

# Core

Common service layer shared by `scene.cli` and `scene.agent`. Provides a unified interface for manipulating scene data, so both the CLI and the LLM-driven agents operate through the same underlying operations rather than each talking to `scene.data` independently. Organized as one module per entity (e.g. `story.py`), each exposing CRUD-style functions that operate on a caller-supplied SQLAlchemy `Session` from `scene.data`, leaving session/transaction lifecycle to the caller.
