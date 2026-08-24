---
archived: false
campaign: c008-story-data-model-v2
created_by: John Hoff
created_on: '2026-08-24T14:23:28Z'
depends_on:
- e004-story-field-rename-cli
kind: scripted
name: e005-story-field-rename-gui
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-24T16:41:37Z'
---

# Story/scene field rename — GUI layer

## Requirements

Update `src/scene/gui/` to use the renamed/added `core` parameters from
`e002-story-field-rename-core`, the last layer in the story-fields path:

- `src/scene/gui/entity_column/story_detail.py`: rename the "Scenario" form
  row/field to "Story Brief" (`scenario_edit` → `story_brief_edit`, wired to
  `story.story_brief`); add a "Generation Guidance" `QPlainTextEdit` row
  wired to `story.generation_guideance`, following the existing
  `style_guidance_edit` pattern (loaded in `load`, saved in
  `_on_save_clicked` via `update_story`).
- `src/scene/gui/story_header.py`: rename its "Scenario" field/row the same
  way (`scenario_edit` → `story_brief_edit`) in the new-story dialog, and
  update the tuple it returns/consumes and the `create_story` call's keyword
  argument.
- `src/scene/gui/entity_column/scenes.py`: rename the "Description" form row
  to "Brief" (`description_edit` → `brief_edit`) and "Length" to "Target
  Length" (`length_edit` → `target_length_edit`); add a "Desired Outcome"
  `QPlainTextEdit` row; add a "Point of View" `QComboBox` row populated from
  `list_characters(session, self.story_id)` plus a leading "(none)" entry
  (character id stored via `setItemData`/`currentData`, following the
  existing `Qt.ItemDataRole.UserRole` convention used for the character/
  location checklists), wired to `scene.pov_character_id` in `_load_detail`
  and `_on_save_clicked`; when `update_scene` raises `ValueError` for a
  cross-story `pov_character_id` (should not normally happen since the combo
  is populated from the scene's own story, but keep the app from crashing if
  it does), show it via `QMessageBox` rather than propagating the exception.

Out of scope: `src/scene/gui/entity_column/characters.py`,
`entity_column/locations.py` (their `description`/`motive` fields are
character/location attributes, unaffected by this rename); any new
GUI surface for `continuity_snapshot` (a later encounter in this campaign).

## Rationale

`scene.gui` is the last layer in the user's requested data → core → agent →
cli → gui ordering for the story-fields path: by this point `core` already
exposes and validates every v2 field, so this encounter is purely about
updating widget labels/bindings and adding the new optional fields'
controls, with no new business logic beyond surfacing the `core`-layer
`ValueError` the GUI hasn't had to handle before (previously only
`scene_character`/`scene_location` assignment could raise it, and those are
silently ignored by construction — the combo is always populated from valid
same-story characters).

## Plan

1. `src/scene/gui/entity_column/story_detail.py`: rename the scenario field
   and add the generation-guidance field, in the widget constructor, `load`,
   and `_on_save_clicked`.
2. `src/scene/gui/story_header.py`: rename the scenario field in the
   new-story dialog and its return/consumption path.
3. `src/scene/gui/entity_column/scenes.py`: rename `description_edit`/
   `length_edit`; add `desired_outcome_edit` and a `pov_character_combo`
   populated in `_load_assignments` (or a new helper) from
   `list_characters`; wire both into `_load_detail` and `_on_save_clicked`;
   wrap the `update_scene` call in `try/except ValueError` showing a
   `QMessageBox.warning` on failure.
4. Update `test/scene/gui/entity_column/test_story_detail.py`,
   `test/scene/gui/test_story_header.py`, and
   `test/scene/gui/entity_column/test_scenes.py` for the renamed/added
   widgets and fields.
5. Run `pdm run lint` and fix any findings.

## Verification

- `pdm run pytest` passes, including the updated `test/scene/gui/**` test
  files listed above.
- `pdm run lint` reports no findings.
- Launch the GUI (per the project's `run` skill, if usable in this
  environment) and confirm the Story panel shows "Story Brief"/"Generation
  Guidance" and the Scenes panel shows "Brief"/"Target Length"/"Desired
  Outcome"/"Point of View", each loading and saving correctly for an
  existing story/scene.
- Grep confirms no remaining references to `scenario`, `.description`, or
  `.length` (as story/scene attributes or GUI field names) anywhere under
  `src/scene/gui/`.

## Log

### Review - 2026-08-24T16:28:38Z - John Hoff

Reviewed against the two world-assigned lore items (linting, unit-testing) and the gui region (no additional region-specific lore). The Plan explicitly runs pdm run lint and requires zero findings, and step 4 updates three test files whose paths correctly mirror their src/scene/gui/... targets per the unit-testing convention, with Verification requiring pdm run pytest to pass -- both lore items are honored. I cross-checked the Plan's described target signatures for create_story/update_story and create_scene/update_scene against the actually-landed src/scene/core/story.py and src/scene/core/scene.py (the explicitly permitted e002 dependency) and they match exactly, including _validate_pov_character's ValueError behavior; I also read the three named GUI source files and confirmed their current field names/kwargs (scenario_edit, description_edit/length_edit, and an update_scene call using now-stale description/length kwargs) match what the Requirements describe as needing renaming, so the Plan is grounded in the real current state rather than assumed. One background claim in the Rationale (that only scene_character/scene_location assignment previously raised ValueError, "silently ignored by construction") was not verified since those files aren't named by the encounter and fall outside the bounded reading surface -- flagged as unverified but not scope-relevant. No lore conflicts found; PASS-WITH-NOTES.

### Completed - 2026-08-24T16:41:37Z - John Hoff

GUI layer updated as planned: story_detail.py and story_header.py renamed their Scenario field to Story Brief (story_brief_edit), and story_detail.py gained a Generation Guidance field. scenes.py renamed Description/Length to Brief/Target Length, added a Desired Outcome field, and added a Point of View QComboBox (populated from list_characters plus a leading "(none)" entry, storing character id via item data) wired to pov_character_id, with the update_scene ValueError wrapped in a QMessageBox.warning instead of propagating. Updated all test/scene/gui/** fixtures and added new coverage for generation_guideance and the POV combo (population, save, and reselecting none after reload).

While verifying, found and fixed two cross-boundary gaps outside any single encounter's file list: test/scene/gui/test_chat_panel.py and test/scene/gui/test_main_window.py both simulate LLM tool-call JSON with the old "scenario" key (exercising the coordinator tool schema renamed in e003, but neither file was in e003's or e005's named scope since chat_panel.py itself has no story/scene field references) -- fixed both to use "story_brief".

test/scene/gui/** is fully green (94 passed) and pdm run lint is clean. This was the last encounter in the story-fields track: the full repo suite now passes end to end (417 passed, 0 failed) with pdm run lint clean -- the story-path (e001-e005) is complete and stable, ready for the generation/continuity-snapshot path (e006-e010) per the user's two-track plan. (One unrelated flaky Textual async-timing test was observed under full-suite load and confirmed non-reproducing on rerun -- pre-existing, not caused by this campaign.)
