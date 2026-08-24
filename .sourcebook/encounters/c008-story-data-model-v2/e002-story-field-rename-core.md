---
archived: false
campaign: c008-story-data-model-v2
created_by: John Hoff
created_on: '2026-08-24T14:22:19Z'
depends_on:
- e001-story-field-rename-data
kind: scripted
name: e002-story-field-rename-core
regions:
- core
status: completed
updated_by: John Hoff
updated_on: '2026-08-24T16:06:24Z'
---

# Story/scene field rename — core service layer

## Requirements

Update `src/scene/core/story.py` and `src/scene/core/scene.py` to match the
renamed/added ORM attributes landed in `e001-story-field-rename-data`
(`Story.story_brief`, `Story.generation_guideance`, `Scene.brief`,
`Scene.target_length`, `Scene.desired_outcome`, `Scene.pov_character_id`):

- `create_story`/`update_story`: rename the `scenario` parameter to
  `story_brief`; add an optional `generation_guideance: str | None = None`
  parameter, applied with the same "only set if not None" pattern already
  used for the other optional fields in `update_story`.
- `create_scene`/`update_scene`: rename `description` parameter to `brief`;
  rename `length` to `target_length`; add optional
  `desired_outcome: str | None = None` and `pov_character_id: int | None =
  None` parameters, applied with the same pattern.
- Enforce the data-model-v2 invariant that a scene's `pov_character_id`, when
  provided and not `None`, must reference a `character` belonging to the same
  `story_id` as the scene — mirroring the existing same-story check in
  `assign_character` (`src/scene/core/scene_character.py`), including its
  `ValueError` convention so callers (CLI, agent tools) can catch and report
  it the same way `scene_character` assignment errors are already handled.

Out of scope: no change to `character.py`, `location.py`,
`scene_character.py`, `scene_location.py`, or `rendering.py`; no
`continuity_snapshot` module (a later encounter in this campaign).

## Rationale

`scene.core` is the shared service layer between `scene.cli` and
`scene.agent`; both depend on its function signatures and parameter names.
Renaming it immediately after the data layer, and before either consumer, is
the middle step in the user's requested data → core → agent → cli → gui
ordering for the story-fields path, and keeps the same-story FK invariant
that SQLite can't itself enforce (per `docs/data-model-v2.md`) next to the
other application-level invariant of the same shape already established for
`scene_character`.

## Plan

1. In `src/scene/core/story.py`:
   - Rename the `scenario` parameter/attribute usage in `create_story` and
     `update_story` to `story_brief`.
   - Add `generation_guideance: str | None = None` to both, setting
     `story.generation_guideance = generation_guideance` in `update_story`
     only when it is not `None` (matching the existing `style_guidance`
     pattern).
2. In `src/scene/core/scene.py`:
   - Rename `description` to `brief` and `length` to `target_length` in
     `create_scene` and `update_scene`.
   - Add `desired_outcome: str | None = None` and `pov_character_id: int |
     None = None` to both, following the existing optional-field pattern.
   - Add a module-level helper (e.g. `_validate_pov_character`) that, given
     a `Session`, `story_id`, and non-`None` `pov_character_id`, loads the
     `Character` and raises `ValueError` if it doesn't exist or its
     `story_id` doesn't match; call it from `create_scene` and `update_scene`
     whenever `pov_character_id` is provided (in `update_scene`, resolve the
     scene's `story_id` from the already-fetched `Scene` row).
3. Update `test/scene/core/test_story.py` and `test/scene/core/test_scene.py`
   for the renamed parameters/attributes and the new optional fields,
   including a test that `create_scene`/`update_scene` raise `ValueError`
   when `pov_character_id` references a character from a different story or
   a nonexistent character.
4. Run `pdm run lint` and fix any findings.

## Verification

- `pdm run pytest` passes, including the updated `test/scene/core/test_story.py`
  and `test/scene/core/test_scene.py`.
- `pdm run lint` reports no findings.
- Grep confirms no remaining references to `scenario=`, `description=`, or
  `length=` as story/scene keyword arguments anywhere under `src/scene/core/`.

## Log

### Review - 2026-08-24T15:47:54Z - John Hoff

Reviewed against the two applicable world lore items (linting, unit-testing); both are explicitly satisfied in the Plan (step 4 runs `pdm run lint`) and Verification (`pdm run pytest` passing, updated tests at test/scene/core/test_story.py and test/scene/core/test_scene.py mirroring the core region per the unit-testing convention, including new-invariant ValueError coverage). Cross-checked the Plan's field references against the actual e001-landed ORM (src/scene/data/story.py, src/scene/data/scene.py) and confirmed story_brief, generation_guideance, brief, target_length, desired_outcome, and pov_character_id all exist as described, and that current src/scene/core/story.py/scene.py still use the pre-rename names, so the work is accurately scoped. The proposed pov_character_id same-story validation correctly mirrors the existing assign_character pattern and ValueError convention in src/scene/core/scene_character.py. No lore conflicts found; approved to proceed.

### Completed - 2026-08-24T16:06:24Z - John Hoff

Core service layer rename implemented as planned: create_story/update_story now take story_brief and generation_guideance; create_scene/update_scene now take brief, target_length, desired_outcome, and pov_character_id, with a new _validate_pov_character helper raising ValueError for a missing or cross-story character (mirroring scene_character.py's assign_character pattern). Updated all test/scene/core/** and test/scene/data/** fixtures that constructed Story/Scene with v1 keyword names. test/scene/core/** is fully green (63 passed, 100% coverage on story.py/scene.py) and pdm run lint is clean. agent/cli/gui remain red as expected -- that's e003-e005.
