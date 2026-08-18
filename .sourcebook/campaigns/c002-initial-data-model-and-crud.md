---
archived: false
created_by: John Hoff
created_on: '2026-08-18T03:48:42Z'
name: c002-initial-data-model-and-crud
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T13:46:05Z'
---

# C002 — Initial Data Model and CRUD

## Scope
Build the initial SQLite data model and the CLI CRUD tooling to manage it, split across three regions:

- `scene.data` — SQLAlchemy ORM models and the SQLite schema.
- `scene.core` — the service layer that mediates data access, wrapping the ORM models behind a shared interface for both the CLI and future LLM agents.
- `scene.cli` — CLI commands for creating, reading, updating, and deleting the data through `scene.core`.

## Log

### Completed - 2026-08-18T13:46:05Z - John Hoff

Delivered the full initial SQLite data model and CLI CRUD tooling across six encounters: e001 (story), e002 (scene + rendering), e003 (character + scene_character), e004 (location + scene_location), e005 (scene.length attribute), and e006 (README data model pointer). Every entity in docs/data-model.md now has a matching scene.data ORM model, scene.core service module, and scene-data CLI sub-command group, with 100% test coverage and zero lint errors maintained throughout. Key patterns established for future campaigns to build on: the model -> core service -> CLI vertical slice per entity; join tables (scene_character, scene_location) exposed as assignment verbs rather than full CRUD, with application-level cross-story enforcement since SQLite's FK pairs alone can't guarantee it; and story-scoped uniqueness/cascade-delete constraints enforced at the ORM layer. No open items were deferred; the scene.agent and scene.gui regions remain untouched, as planned, for future campaigns.
