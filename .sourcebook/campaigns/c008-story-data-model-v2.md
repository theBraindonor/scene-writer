---
archived: false
created_by: John Hoff
created_on: '2026-08-24T14:14:32Z'
name: c008-story-data-model-v2
status: completed
updated_by: John Hoff
updated_on: '2026-08-28T21:00:35Z'
---

# Story data model v2 refactor

## Purpose

Refactor story tracking and generation to implement the schema in
`docs/data-model-v2.md` and the prompt strategy in `docs/prompt-guidance.md`.
This is a cross-cutting change: it touches the `data`, `core`, `agent`,
`cli`, and `gui` regions, since the renamed/added columns and the new
`continuity_snapshot` entity flow from the SQLite schema up through the
service layer, the coordinator/rendering agents' prompt construction, the
CLI commands, and the GUI panels that read or edit story/scene fields.

## Scope — data model (`docs/data-model-v2.md`)

Concrete, required schema changes (not aliases — rename in place, update
every read/write):

- `story.scenario` → `story.story_brief`
- `scene.description` → `scene.brief`
- `scene.length` → `scene.target_length`
- Add `story.generation_guideance` (optional; the misspelling is intentional
  per the design doc)
- Add `scene.pov_character_id` (optional FK to `character`, same-story
  invariant enforced in application logic)
- Add `scene.desired_outcome` (optional)
- Add new `continuity_snapshot` table (one row per story/`through_scene_id`,
  holding a single `narrative_state` text field)

Destructive changes to the local SQLite tables are acceptable for this
campaign — no migration path or backward-compatible aliasing is required.
Existing data in `data/` may be dropped/recreated.

No entity, relationship, constraint, or rendering-selection behavior already
in place is being removed. `rendering` and its one-active-per-scene
invariant are unchanged by this campaign.

## Scope — prompt strategy (`docs/prompt-guidance.md`)

`prompt-guidance.md` is aspirational: it captures the overall flow worked
out between the user and their AI assistant, not a literal spec. Prompt
construction updates across `scene.agent` (and any coordinator/rendering
tool code that assembles prompt context) should follow its *shape*:

- Split scene-writing and continuity-editing into distinct prompt
  responsibilities (same or different underlying model).
- Build the scene-writer prompt from stable story reference (`story_brief`,
  `style_guidance`, `generation_guideance`, assigned character/location
  cards) + the current continuity snapshot + the scene-specific request
  (`brief`, `required_actions`, `pov_character_id`, `desired_outcome`,
  `target_length`).
- Render reference data as compact labeled prose cards for the model, not
  raw serialized rows.
- Generate and persist a `continuity_snapshot` after each accepted
  rendering; invalidate and regenerate snapshots forward from a scene whose
  active rendering changes.

Actual implementation (prompt template structure, where continuity-editing
lives in the agent/coordinator pipeline, how snapshot regeneration is
triggered) may differ in the details from the document — it is guidance for
intent, not a contract to match line-for-line.

## Regions touched

`data`, `core`, `agent`, `cli`, `gui` — this campaign's encounters are
expected to span all five.

## Notes

- Existing lore (`linting`, `unit-testing`) applies throughout: ruff-clean,
  120-char lines, and pytest coverage for new/changed code before any
  encounter is marked complete.
- Break the work into encounters along natural seams (e.g. schema + data
  layer first, then core/service layer, then agent prompt construction,
  then CLI, then GUI) so each encounter has a coherent, independently
  verifiable unit of change. Later encounters may depend on earlier ones
  via `encounter_assign_dependency`.

## Log

### Completed - 2026-08-28T21:00:35Z - John Hoff

All 11 planned encounters landed: the story/scene field renames (scenario→story_brief, description→brief, length→target_length) plus the new generation_guideance and pov_character_id/desired_outcome fields were propagated through data, core, agent, cli, and gui; the continuity_snapshot entity and its generation/invalidation flow were added end-to-end; and a rendering-agent token-budget bug found along the way was fixed. Prompt construction now follows the shape described in docs/prompt-guidance.md (stable story reference + continuity snapshot + scene-specific request). Data model v2 is complete and in use.
