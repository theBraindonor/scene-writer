---
archived: false
campaign: c008-story-data-model-v2
created_by: John Hoff
created_on: '2026-08-24T14:22:41Z'
depends_on:
- e002-story-field-rename-core
kind: scripted
name: e003-story-field-rename-agent
regions:
- agent
status: completed
updated_by: John Hoff
updated_on: '2026-08-24T16:21:40Z'
---

# Story/scene field rename — agent layer

## Requirements

Update `src/scene/agent/` to use the renamed/added `core` parameters from
`e002-story-field-rename-core` (`story_brief`, `generation_guideance`,
`brief`, `target_length`, `desired_outcome`, `pov_character_id`), and start
folding the new fields into prompt construction per the "scene-specific
request" section of `docs/prompt-guidance.md` — without yet introducing the
continuity snapshot (a later encounter in this campaign):

- `src/scene/agent/coordinator/tools/story.py`: rename the `scenario`
  tool-schema property and handler argument to `story_brief` on
  `create_story`/`get_story`/`list_stories`/`update_story`; add an optional
  `generation_guideance` property/argument, passed through to
  `core.story.create_story`/`update_story`; update `_story_dict` and every
  tool `description` string that currently says "scenario".
- `src/scene/agent/coordinator/tools/scene.py`: rename `description` to
  `brief` and `length` to `target_length` on every affected tool; add
  optional `desired_outcome` and `pov_character_id` properties/arguments,
  passed through to `core.scene.create_scene`/`update_scene`; update
  `_scene_dict` and tool `description` strings; catch the `ValueError` that
  `core.scene.create_scene`/`update_scene` now raise for a cross-story
  `pov_character_id` and return it as an error dict, matching the existing
  error-dict convention in this module (not the CLI's `typer.Exit` pattern).
- `src/scene/agent/coordinator/loop.py`: update `DEFAULT_SYSTEM_PROMPT`'s
  field-name references ("scenario" → "story brief"; "description" →
  "brief"; "length" → "target length") and mention the new
  `generation_guideance`, `pov_character_id`, and `desired_outcome` fields
  the coordinator can now view/edit.
- `src/scene/agent/rendering.py`:
  - Update `_scene_detail_text` and `build_render_messages` for the renamed
    `Scene.brief`/`Scene.target_length` and `Story.story_brief` attributes.
  - Add `Story.generation_guideance` to the system-prompt story reference
    section in `build_render_messages`, when present (following the existing
    `if story.style_guidance:` pattern).
  - Add `Scene.desired_outcome` to `_scene_detail_text`, when present.
  - When `scene.pov_character_id` is set, resolve the character (via
    `scene.core.character.get_character`) and include a point-of-view
    instruction line in `_scene_detail_text` naming that character.

Out of scope: the continuity-editor role, `continuity_snapshot` generation or
consumption, and changing the existing full-prior-scenes-as-messages strategy
in `build_render_messages` — `docs/prompt-guidance.md`'s guidance to prefer a
compact continuity snapshot over full prior renderings is implemented in the
generation-path encounters later in this campaign, once
`continuity_snapshot` exists end-to-end.

## Rationale

`scene.agent` is the third layer in the user's requested data → core → agent
→ cli → gui ordering for the story-fields path: it must compile against the
renamed `core` signatures from `e002-story-field-rename-core` before either
CLI consumer is touched. Bringing `pov_character_id`/`desired_outcome`/
`generation_guideance` into the coordinator tools and the rendering prompt
now (while still using the existing full-history rendering strategy) keeps
this encounter's surface area to "use the v2 fields" rather than also
reworking the prompt architecture, which is deliberately deferred to the
generation-path (continuity-snapshot) encounters per the user's two-track
plan.

## Plan

1. `src/scene/agent/coordinator/tools/story.py`: rename `scenario` →
   `story_brief` throughout (schema properties, handler arguments,
   `_story_dict`, tool descriptions); add `generation_guideance` as an
   optional schema property threaded into `create_story_handler` and
   `update_story_handler`, and reflected in `_story_dict`.
2. `src/scene/agent/coordinator/tools/scene.py`: rename `description` →
   `brief` and `length` → `target_length` throughout; add optional
   `desired_outcome` and `pov_character_id` schema properties threaded into
   `create_scene_handler`/`update_scene_handler`; wrap the `core.scene`
   calls in a `try/except ValueError` that returns `{"error": str(error)}`
   for the cross-story `pov_character_id` case; update `_scene_dict` and
   tool descriptions.
3. `src/scene/agent/coordinator/loop.py`: update `DEFAULT_SYSTEM_PROMPT`'s
   field-name list.
4. `src/scene/agent/rendering.py`: apply the attribute renames; add
   `generation_guideance` to the system prompt section; add
   `desired_outcome` and a POV instruction line to `_scene_detail_text`.
5. Update `test/scene/agent/coordinator/tools/test_story.py`,
   `test/scene/agent/coordinator/tools/test_scene.py` (including a case for
   the cross-story `pov_character_id` error), `test/scene/agent/test_rendering.py`,
   and `test/scene/agent/coordinator/test_loop.py` if it asserts on
   `DEFAULT_SYSTEM_PROMPT` content.
6. Run `pdm run lint` and fix any findings.

## Verification

- `pdm run pytest` passes, including the updated `test/scene/agent/**` test
  files listed above.
- `pdm run lint` reports no findings.
- Grep confirms no remaining references to `scenario`, `.description`, or
  `.length` (as story/scene attributes or tool-schema property names)
  anywhere under `src/scene/agent/`.

## Log

### Review - 2026-08-24T16:08:36Z - John Hoff

Reviewed against the two applicable world lore items (linting, unit-testing) — both are explicitly satisfied by Plan step 6 (pdm run lint) and step 5 plus the Verification section (updated tests under test/scene/agent/** mirroring the modified src/scene/agent/** modules, pdm run pytest passing). Cross-checked the Plan's technical claims against the already-landed e002 dependency (src/scene/core/story.py, src/scene/core/scene.py) and the cited docs/prompt-guidance.md section, and against the current pre-rename state of the four src/scene/agent files the Plan targets: the described function signatures, the ValueError/error-dict handling convention, the existing "if story.style_guidance:" pattern, and the scene.core.character.get_character helper all match what's actually in the repo, and the old scenario/description/length references are indeed still present, confirming the need for this encounter. One minor unspecified edge case (a stale/deleted pov_character_id returning None from get_character in rendering) is noted but does not conflict with lore. No lore conflicts found; approved to proceed.

### Completed - 2026-08-24T16:21:40Z - John Hoff

Agent layer updated as planned: coordinator/tools/story.py and tools/scene.py renamed to story_brief/brief/target_length and gained generation_guideance/desired_outcome/pov_character_id schema properties, with a try/except ValueError -> error-dict wrapper around the new cross-story pov_character_id validation. loop.py's DEFAULT_SYSTEM_PROMPT and rendering.py's build_render_messages/_scene_detail_text were updated for the renamed attributes and gained generation_guideance, desired_outcome, and a POV instruction line (guarded against a stale/deleted pov_character_id per the reviewer's note). Updated all test/scene/agent/** fixtures and added new test coverage for generation_guideance, desired_outcome, and both pov_character_id error paths. test/scene/agent/** is fully green (136 passed) and pdm run lint is clean. cli/gui remain red as expected -- that's e004-e005.
