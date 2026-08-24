---
archived: false
campaign: c008-story-data-model-v2
created_by: John Hoff
created_on: '2026-08-24T14:23:01Z'
depends_on:
- e003-story-field-rename-agent
kind: scripted
name: e004-story-field-rename-cli
regions:
- cli
status: completed
updated_by: John Hoff
updated_on: '2026-08-24T16:27:25Z'
---

# Story/scene field rename — CLI layer

## Requirements

Update `src/scene/cli/` to use the renamed/added `core` parameters from
`e002-story-field-rename-core`:

- `src/scene/cli/data.py` (`scene-data` console script):
  - `story create`/`story get`/`story update`: rename the `scenario`
    argument/option and its `typer.echo` line to `story_brief` (echoed as
    `story_brief: ...`); add an optional `generation_guideance` option to
    `create`/`update`, echoed by `get`.
  - `scene create`/`scene get`/`scene update`: rename `description` to
    `brief` and `length` to `target_length` (arguments, options, and
    `typer.echo` lines); add optional `desired_outcome` and
    `pov_character_id` options to `create`/`update`, echoed by `get`; when
    `create_scene`/`update_scene` raises `ValueError` for a cross-story
    `pov_character_id`, catch it and exit the same way `scene-character
    assign` already does (`typer.echo(str(error))` + `typer.Exit(code=1)`).
- `src/scene/cli/render_app.py`: update `_scene_detail_text` for
  `Scene.brief`/`Scene.target_length` and add `Scene.desired_outcome`
  (following the existing "Required actions: ... / Length: ..." line
  pattern); it calls `scene.agent.rendering.build_render_messages`, already
  updated in `e003-story-field-rename-agent`, so no other change is needed
  there.
- `src/scene/cli/coordinator_app.py`: update the story/scene summary lines
  that currently print "Scenario:", scene "Description:", and scene
  "Length:" for the renamed fields, and add lines for
  `generation_guideance`, `desired_outcome`, and the POV character (when
  set), matching the existing summary format.

Out of scope: `src/scene/cli/coordinator.py` (no scenario/description/length
references found); any change to command names or console-script entry
points.

## Rationale

`scene.cli` is the fourth layer in the user's requested data → core → agent
→ cli → gui ordering: `scene-data` is "the primary interface until a GUI
exists" per `CLAUDE.md`, so it must expose every v2 field the same way the
coordinator agent's tools do, and both `render_app.py` and
`coordinator_app.py` need their own display strings updated so the CLI
doesn't silently keep printing v1 field names/labels after the layers below
it have moved to v2.

## Plan

1. `src/scene/cli/data.py`: apply the parameter renames and additions
   described above to `story create`/`get`/`update` and `scene
   create`/`get`/`update`, following the existing option-per-field and
   plain-`typer.echo` conventions already used in this file.
2. `src/scene/cli/render_app.py`: update `_scene_detail_text`'s field
   references and add a `Desired outcome:` line.
3. `src/scene/cli/coordinator_app.py`: update the "Scenario:"/"Description:"/
   "Length:" lines (and surrounding logic) for the renamed fields, adding
   `generation_guideance`, `desired_outcome`, and POV character lines
   consistent with the existing summary format.
4. Update `test/scene/cli/test_data.py`, `test/scene/cli/test_render_app.py`,
   and `test/scene/cli/test_coordinator_app.py` for the renamed
   options/output and the new fields, including a CLI-level test for the
   cross-story `pov_character_id` error exit path.
5. Run `pdm run lint` and fix any findings.

## Verification

- `pdm run pytest` passes, including the updated `test/scene/cli/**` test
  files listed above.
- `pdm run lint` reports no findings.
- `pdm run scene-data story create --help` and `pdm run scene-data scene
  create --help` show `story-brief`/`brief`/`target-length` (not `scenario`/
  `description`/`length`) among their options.
- Grep confirms no remaining references to `scenario`, `.description`, or
  `.length` (as story/scene attributes, options, or display labels)
  anywhere under `src/scene/cli/`.

## Log

### Review - 2026-08-24T16:23:15Z - John Hoff

Reviewed e004-story-field-rename-cli against the linting and unit-testing lore (both explicitly and correctly addressed by Plan steps 4-5 and the Verification section) and against the cli region's service-layer convention (the Plan only threads renamed parameters through existing scene.core calls, no direct scene.data access). Cross-checked the Plan's assumptions about already-landed work in src/scene/core/story.py, src/scene/core/scene.py, and src/scene/agent/rendering.py against the actual code and confirmed the described signatures (story_brief/generation_guideance, brief/target_length/desired_outcome/pov_character_id plus _validate_pov_character's ValueError, and build_render_messages's positional signature) all match what e002/e003 landed; also confirmed the current src/scene/cli/*.py files still use the pre-rename field names exactly as described (and are presently broken against the renamed core layer, which correctly motivates this encounter) and that the "out of scope: coordinator.py" claim holds on inspection. No lore conflicts or unverifiable gaps found. PASS-WITH-NOTES.

### Completed - 2026-08-24T16:27:25Z - John Hoff

CLI layer updated as planned: scene-data's story/scene create/get/update commands renamed to story-brief/brief/target-length and gained --generation-guideance/--desired-outcome/--pov-character-id options, with the cross-story pov_character_id ValueError caught and exited the same way scene-character assign already does. render_app.py's scene detail text and coordinator_app.py's story/scene summary panes updated for the renamed fields plus generation guidance, desired outcome, and POV character lines. Updated all test/scene/cli/** fixtures, tool-call JSON payloads, and CLI invocations, and added new coverage for generation_guideance, desired_outcome, and both pov_character_id error paths. test/scene/cli/** is fully green (97 passed), pdm run lint is clean, and --help output confirms the new option names (story-brief/brief/target-length/desired-outcome/pov-character-id). gui remains red as expected -- that's e005, the last encounter in the story-fields path.
