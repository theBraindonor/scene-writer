---
archived: false
campaign: c008-story-data-model-v2
created_by: John Hoff
created_on: '2026-08-24T14:19:54Z'
depends_on: []
kind: scripted
name: e001-story-field-rename-data
regions:
- data
status: completed
updated_by: John Hoff
updated_on: '2026-08-24T15:30:09Z'
---

# Story/scene field rename — data layer

## Requirements

Implement the "story path" portion of `docs/data-model-v2.md` at the ORM/schema
level only (`src/scene/data/`), excluding `continuity_snapshot` (deferred to a
later encounter in this campaign):

- `Story`: rename `scenario` → `story_brief` (column + `CheckConstraint` name
  and expression); add optional `generation_guideance: str | None`.
- `Scene`: rename `description` → `brief` (column + `CheckConstraint` name and
  expression); rename `length` → `target_length`; add optional
  `desired_outcome: str | None`; add optional `pov_character_id: int | None`
  as a `ForeignKey("character.id", ondelete="SET NULL")`, plus an index on it
  (matching the `idx_scene_pov_character_id` index in the design doc).
- No migration path is required. Destructive change is acceptable: the
  gitignored `data/scene.db` file is deleted locally and recreated via the
  existing `init_db`/`create_all` path, which does not need to alter an
  existing table in place.

Out of scope for this encounter: enforcing "the pov character must belong to
the same story as the scene" (application-logic, not expressible as a plain
SQLite FK per the design doc) — that belongs in the `core` service layer
encounter that follows this one. Also out of scope: any change to
`character`, `location`, `scene_character`, `scene_location`, or `rendering`
tables, and the `continuity_snapshot` table itself.

## Rationale

`docs/data-model-v2.md` states these are intentional schema changes, not
aliases, and that code, queries, and prompt builders must use the v2 names.
Doing the data-layer rename first, as its own reviewable/verifiable unit,
lets every layer above it (`core`, `agent`, `cli`, `gui`) be updated against a
stable, already-correct schema rather than a moving target — matching the
user's explicit request to proceed data → core → agent → cli → gui for the
story-fields path before repeating the same layer sequence for the
generation/continuity-snapshot path.

## Plan

1. In `src/scene/data/story.py`:
   - Rename the `scenario` mapped column to `story_brief` (keep it
     `nullable=False`).
   - Rename `ck_story_scenario_not_blank` to `ck_story_story_brief_not_blank`
     and update its `length(trim(...))` expression to reference
     `story_brief`.
   - Add `generation_guideance: Mapped[str | None] = mapped_column(String,
     nullable=True)`.
2. In `src/scene/data/scene.py`:
   - Rename the `description` mapped column to `brief` (keep it
     `nullable=False`).
   - Rename `ck_scene_description_not_blank` to `ck_scene_brief_not_blank`
     and update its expression to reference `brief`.
   - Rename the `length` mapped column to `target_length`.
   - Add `desired_outcome: Mapped[str | None] = mapped_column(String,
     nullable=True)`.
   - Add `pov_character_id: Mapped[int | None] = mapped_column(ForeignKey
     ("character.id", ondelete="SET NULL"), nullable=True)` and an
     `Index("idx_scene_pov_character_id", "pov_character_id")` in
     `__table_args__` (following the `Index` pattern already used in
     `src/scene/data/character.py`).
3. Delete the local `data/scene.db` (if present) so it is recreated with the
   new schema on next use; it is gitignored and campaign scope permits data
   loss.
4. Update `test/scene/data/test_story.py` and `test/scene/data/test_scene.py`
   for the renamed/added columns and constraints (including a test that the
   blank-`story_brief`/blank-`brief` check constraints still fire under their
   new names, and that `pov_character_id` accepts `NULL` and a valid
   `character.id`).
5. Run `pdm run lint` and fix any findings.

## Verification

- `pdm run pytest` passes, including the updated `test/scene/data/test_story.py`
  and `test/scene/data/test_scene.py`.
- `pdm run lint` reports no findings.
- Grep confirms no remaining references to `Story.scenario`, `Scene.description`,
  or `Scene.length` anywhere under `src/scene/data/`.

## Log

### Review - 2026-08-24T14:45:39Z - John Hoff

Reviewed against the two applicable lore items (linting, unit-testing) plus the cited docs/data-model-v2.md for internal consistency. The Plan honors both lore items directly: it includes an explicit `pdm run lint` step with zero-findings verification, and updates test/scene/data/test_story.py / test/scene/data/test_scene.py in the established test-mirrors-src convention with `pdm run pytest` required to pass. All renamed/added columns, types, the new FK, and the new index match docs/data-model-v2.md's SQL exactly, and the existing Scene.length/character.py code confirms the plan's assumptions (no type change needed for target_length; the cited Index pattern exists as described). One minor, non-blocking note: the Plan names explicit test cases for the renamed check constraints and the new FK, but only implicitly covers the two new plain optional fields (generation_guideance, desired_outcome) — worth confirming at verification time that they get direct test coverage too. No lore conflicts found.

### Completed - 2026-08-24T15:30:09Z - John Hoff

Data-layer rename implemented as planned: Story.scenario -> story_brief (+ generation_guideance added), Scene.description -> brief, Scene.length -> target_length (+ desired_outcome and pov_character_id added, with its FK/index). All test/scene/data/** tests pass (26 passed) and pdm run lint is clean. As expected, this leaves core/agent/cli/gui test fixtures red (they still construct Story/Scene with the old v1 keyword names, which SQLAlchemy's generated __init__ now rejects) -- that breakage is exactly what e002-e005 exist to fix, layer by layer.
