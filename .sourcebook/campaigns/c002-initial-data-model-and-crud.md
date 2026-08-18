---
archived: false
created_by: John Hoff
created_on: '2026-08-18T03:48:42Z'
name: c002-initial-data-model-and-crud
status: draft
updated_by: John Hoff
updated_on: '2026-08-18T03:48:42Z'
---

# C002 — Initial Data Model and CRUD

## Scope
Build the initial SQLite data model and the CLI CRUD tooling to manage it, split across three regions:

- `scene.data` — SQLAlchemy ORM models and the SQLite schema.
- `scene.core` — the service layer that mediates data access, wrapping the ORM models behind a shared interface for both the CLI and future LLM agents.
- `scene.cli` — CLI commands for creating, reading, updating, and deleting the data through `scene.core`.
