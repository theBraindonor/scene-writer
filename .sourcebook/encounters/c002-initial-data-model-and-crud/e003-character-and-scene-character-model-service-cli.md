---
archived: false
campaign: c002-initial-data-model-and-crud
created_by: John Hoff
created_on: '2026-08-18T04:51:16Z'
depends_on: []
kind: scripted
name: e003-character-and-scene-character-model-service-cli
regions:
- cli
- core
- data
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T04:59:01Z'
---

# E003 — Character and Scene Cast Assignment Model, Service, and CLI

## Requirements
- Add a SQLAlchemy ORM `Character` model to `scene.data`, matching `docs/data-model.md`'s `character` table and constraints: `id`, `story_id` (FK to `story.id`, cascade delete), `name` (required, non-blank, unique per story), `description` (optional), `motive` (optional).
- Add a SQLAlchemy ORM `SceneCharacter` model to `scene.data`, matching `docs/data-model.md`'s `scene_character` join table: composite primary key (`scene_id`, `character_id`), both FKs cascade delete (to `scene.id` and `character.id` respectively), with an index on `character_id`.
- Add a `scene.core.character` service module following the `story.py`/`scene.py` pattern (functions operating on a caller-supplied `Session`): create, get, list (scoped to a `story_id`), update, delete.
- Add a `scene.core.scene_character` service module exposing cast-assignment operations: assign a character to a scene, unassign a character from a scene, list characters assigned to a scene, list scenes a character is assigned to. Per `docs/data-model.md`'s explicit note under "Scene cast assignment", SQLite's plain FK pair cannot guarantee a scene and its assigned character share the same story — the assign operation must enforce this itself (rejecting a cross-story assignment) since the schema alone cannot.
- Extend the `scene-data` CLI (`scene.cli.data`) with a `character` Typer sub-command group (`scene-data character create|list|get|update|delete`), following the same command shape as the existing `story`/`scene` groups, and a `scene-character` Typer sub-command group (`scene-data scene-character assign|unassign|list-for-scene|list-for-character`) exposing the cast-assignment operations.
- Cover the new models, service functions, and CLI commands with unit tests mirroring `src/` under `test/`, per the `unit-testing` lore, using an isolated (non-production) database for every test — including tests for the per-story name-uniqueness constraint, the composite-key/duplicate-assignment constraint, and the cross-story assignment rejection.

## Rationale
This is the third encounter of `c002-initial-data-model-and-crud`, extending the vertical-slice pattern established by `e001-story-model-service-cli` and `e002-scene-rendering-model-service-cli` (model → core service → CLI) to `character` and its `scene_character` join table, the next entities in `docs/data-model.md`'s proposed schema. Character and scene_character are grouped into one encounter because the join table only exists in relation to characters (and scenes, already delivered by `e002`), mirroring how `e002` grouped scene with its dependent rendering entity. Unlike `rendering`, `scene_character` has no attributes of its own beyond its two identifiers, so its CLI surface is assignment verbs rather than full CRUD.

## Plan
1. In `scene.data`, add `character.py` defining the `Character` model (matching `docs/data-model.md`'s `character` table: FK to `story` with cascade delete, `name` non-blank check, `(story_id, name)` unique constraint, optional `description`/`motive`), plus an index on `story_id` mirroring `idx_character_story_id`.
2. In `scene.data`, add `scene_character.py` defining the `SceneCharacter` model (composite primary key on `scene_id`/`character_id`, both FKs cascade delete to `scene.id`/`character.id`), plus an index on `character_id` mirroring `idx_scene_character_character_id`.
3. In `scene.core`, add `character.py` with `create_character`, `get_character`, `list_characters(session, story_id)`, `update_character`, and `delete_character`, following `scene.py`'s style.
4. In `scene.core`, add `scene_character.py` with `assign_character(session, scene_id, character_id)` (loading both the scene and character, raising `ValueError` if either is missing or if `scene.story_id != character.story_id`, before inserting the join row), `unassign_character(session, scene_id, character_id)`, `list_characters_for_scene(session, scene_id)`, and `list_scenes_for_character(session, character_id)`.
5. In `scene.cli.data`, add a `character` Typer sub-app (`scene-data character create|list|get|update|delete`) and a `scene-character` Typer sub-app (`scene-data scene-character assign|unassign|list-for-scene|list-for-character`), registered on the existing `app` alongside `story`/`scene`/`rendering`.
6. Add unit tests under `test/scene/data`, `test/scene/core`, and `test/scene/cli` covering the `Character` model (including its per-story name-uniqueness constraint), the `SceneCharacter` model (including its composite-key duplicate-assignment constraint), both new service modules (including the cross-story assignment rejection in `scene.core.scene_character`), and both new CLI sub-command groups, all against an isolated test database.

## Verification
- Run `pdm run pytest` with no extra arguments and confirm all tests pass, including the new character/scene_character tests, with an HTML coverage report generated by default.
- Run `pdm run lint` and confirm zero errors.
- Manually run `scene-data character --help` and `scene-data scene-character --help` (e.g. via `pdm run scene-data character --help`) and confirm both sub-command groups are registered and listed.

## Log

### Review - 2026-08-18T04:55:13Z - John Hoff

Reviewed against the two applicable world lore items (linting, unit-testing) — no region-specific lore is assigned to cli/core/data. The Plan and Verification explicitly require `pdm run lint` with zero errors and `pdm run pytest` with all tests passing and default HTML coverage, with new tests placed under `test/scene/data`, `test/scene/core`, and `test/scene/cli` mirroring `src/`, per the unit-testing lore's path-mirroring rule. The Character and SceneCharacter model definitions, cascade-delete and uniqueness constraints, and the application-level cross-story assignment check all match `docs/data-model.md` (cited in the encounter and read directly to verify), and the planned module layout follows the existing `story.py`/`scene.py`/`rendering.py` precedent in `scene.data`/`scene.core`/`scene.cli`. No conflicts or gaps found; PASS-WITH-NOTES.

### Completed - 2026-08-18T04:59:01Z - John Hoff

Verified: pdm run pytest passes all 93 tests with 100% coverage across the new scene.data.character/scene_character models, scene.core.character/scene_character services, and scene-data character/scene-character CLI groups; pdm run lint reports zero errors; pdm run scene-data character --help and scene-character --help both list all sub-commands. Per-story name uniqueness, composite-key duplicate-assignment, and cross-story assignment rejection are all covered by unit tests.
