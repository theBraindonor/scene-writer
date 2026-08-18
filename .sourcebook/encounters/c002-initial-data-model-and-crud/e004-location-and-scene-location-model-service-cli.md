---
archived: false
campaign: c002-initial-data-model-and-crud
created_by: John Hoff
created_on: '2026-08-18T04:59:51Z'
depends_on: []
kind: scripted
name: e004-location-and-scene-location-model-service-cli
regions:
- cli
- core
- data
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T05:04:01Z'
---

# E004 — Location and Scene Location Assignment Model, Service, and CLI

## Requirements
- Add a SQLAlchemy ORM `Location` model to `scene.data`, matching `docs/data-model.md`'s `location` table and constraints: `id`, `story_id` (FK to `story.id`, cascade delete), `name` (required, non-blank, unique per story), `description` (optional).
- Add a SQLAlchemy ORM `SceneLocation` model to `scene.data`, matching `docs/data-model.md`'s `scene_location` join table: composite primary key (`scene_id`, `location_id`), both FKs cascade delete (to `scene.id` and `location.id` respectively), with an index on `location_id`.
- Add a `scene.core.location` service module following the `story.py`/`scene.py`/`character.py` pattern (functions operating on a caller-supplied `Session`): create, get, list (scoped to a `story_id`), update, delete.
- Add a `scene.core.scene_location` service module exposing location-assignment operations: assign a location to a scene, unassign a location from a scene, list locations assigned to a scene, list scenes a location is assigned to. Per `docs/data-model.md`'s explicit note under "Scene location assignment", SQLite's plain FK pair cannot guarantee a scene and its assigned location share the same story — the assign operation must enforce this itself (rejecting a cross-story assignment) since the schema alone cannot, mirroring the same enforcement `e003` added for `scene.core.scene_character`.
- Extend the `scene-data` CLI (`scene.cli.data`) with a `location` Typer sub-command group (`scene-data location create|list|get|update|delete`), following the same command shape as the existing `story`/`scene`/`character` groups, and a `scene-location` Typer sub-command group (`scene-data scene-location assign|unassign|list-for-scene|list-for-location`) exposing the location-assignment operations.
- Cover the new models, service functions, and CLI commands with unit tests mirroring `src/` under `test/`, per the `unit-testing` lore, using an isolated (non-production) database for every test — including tests for the per-story name-uniqueness constraint, the composite-key/duplicate-assignment constraint, and the cross-story assignment rejection.

## Rationale
This is the fourth encounter of `c002-initial-data-model-and-crud`, extending the vertical-slice pattern established by `e001-story-model-service-cli`, `e002-scene-rendering-model-service-cli`, and `e003-character-and-scene-character-model-service-cli` (model → core service → CLI) to `location` and its `scene_location` join table, the final entities in `docs/data-model.md`'s proposed schema. Location and scene_location are grouped into one encounter for the same reason character and scene_character were in `e003`: the join table only exists in relation to its owning entity (and scenes, already delivered by `e002`). `scene_location` has no attributes of its own beyond its two identifiers, so its CLI surface is assignment verbs rather than full CRUD, and its cross-story enforcement need mirrors `scene_character`'s exactly.

## Plan
1. In `scene.data`, add `location.py` defining the `Location` model (matching `docs/data-model.md`'s `location` table: FK to `story` with cascade delete, `name` non-blank check, `(story_id, name)` unique constraint, optional `description`), plus an index on `story_id` mirroring `idx_location_story_id`.
2. In `scene.data`, add `scene_location.py` defining the `SceneLocation` model (composite primary key on `scene_id`/`location_id`, both FKs cascade delete to `scene.id`/`location.id`), plus an index on `location_id` mirroring `idx_scene_location_location_id`.
3. In `scene.core`, add `location.py` with `create_location`, `get_location`, `list_locations(session, story_id)`, `update_location`, and `delete_location`, following `character.py`'s style.
4. In `scene.core`, add `scene_location.py` with `assign_location(session, scene_id, location_id)` (loading both the scene and location, raising `ValueError` if either is missing or if `scene.story_id != location.story_id`, before inserting the join row), `unassign_location(session, scene_id, location_id)`, `list_locations_for_scene(session, scene_id)`, and `list_scenes_for_location(session, location_id)`, following `scene_character.py`'s style.
5. In `scene.cli.data`, add a `location` Typer sub-app (`scene-data location create|list|get|update|delete`) and a `scene-location` Typer sub-app (`scene-data scene-location assign|unassign|list-for-scene|list-for-location`), registered on the existing `app` alongside `story`/`scene`/`rendering`/`character`/`scene-character`.
6. Add unit tests under `test/scene/data`, `test/scene/core`, and `test/scene/cli` covering the `Location` model (including its per-story name-uniqueness constraint), the `SceneLocation` model (including its composite-key duplicate-assignment constraint), both new service modules (including the cross-story assignment rejection in `scene.core.scene_location`), and both new CLI sub-command groups, all against an isolated test database.

## Verification
- Run `pdm run pytest` with no extra arguments and confirm all tests pass, including the new location/scene_location tests, with an HTML coverage report generated by default.
- Run `pdm run lint` and confirm zero errors.
- Manually run `scene-data location --help` and `scene-data scene-location --help` (e.g. via `pdm run scene-data location --help`) and confirm both sub-command groups are registered and listed.

## Log

### Review - 2026-08-18T05:01:59Z - John Hoff

Reviewed e004 against the two applicable lore items (linting, unit-testing): the Plan and Verification sections explicitly gate completion on `pdm run lint` (zero errors, ruff 120-char) and `pdm run pytest` (default HTML coverage, all passing, with new tests placed under `test/scene/data`, `test/scene/core`, and `test/scene/cli` mirroring `src/`), fully satisfying both. The model/service/CLI design also matches `docs/data-model.md`'s `location`/`scene_location` definitions verbatim, and the referenced `character.py`/`scene_character.py`/`cli/data.py` precedents it plans to mirror already exist in the assigned regions, confirming feasibility. No lore conflicts or gaps found; passing with no required changes.

### Completed - 2026-08-18T05:04:01Z - John Hoff

Verified: pdm run pytest passes all 123 tests with 100% coverage across the new scene.data.location/scene_location models, scene.core.location/scene_location services, and scene-data location/scene-location CLI groups; pdm run lint reports zero errors; pdm run scene-data location --help and scene-location --help both list all sub-commands. Per-story name uniqueness, composite-key duplicate-assignment, and cross-story assignment rejection are all covered by unit tests. This completes the data-model/CRUD vertical slice for every entity in docs/data-model.md.
