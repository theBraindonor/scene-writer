---
archived: false
campaign: c008-story-data-model-v2
created_by: John Hoff
created_on: '2026-08-24T14:26:16Z'
depends_on:
- e006-continuity-snapshot-data
kind: scripted
name: e007-continuity-snapshot-core
regions:
- core
status: completed
updated_by: John Hoff
updated_on: '2026-08-24T18:17:35Z'
---

# Continuity snapshot — core service layer

## Requirements

Add `src/scene/core/continuity_snapshot.py`, the service layer over the
`ContinuitySnapshot` model from `e006-continuity-snapshot-data`, plus the
invalidation behavior `docs/data-model-v2.md` and `docs/prompt-guidance.md`
both require: when a scene's active rendering changes, its snapshot and
every later scene's snapshot in that story become stale and must be removed
before being used as continuity context again.

- `create_snapshot(session, story_id, through_scene_id, narrative_state) ->
  ContinuitySnapshot`: creates a row; raises `ValueError` if
  `through_scene_id` does not belong to `story_id` (mirroring the
  cross-story `ValueError` convention from `e002-story-field-rename-core`)
  and if a snapshot for that `(story_id, through_scene_id)` pair already
  exists (the design doc guarantees "at most one").
- `get_snapshot(session, story_id, through_scene_id) -> ContinuitySnapshot |
  None`.
- `get_preceding_snapshot(session, story_id, scene_id) ->
  ContinuitySnapshot | None`: given a target scene, returns the snapshot
  for the immediately preceding scene in that story's `position` order (the
  "snapshot through the immediately preceding accepted scene" `docs/
  prompt-guidance.md` calls for), or `None` if the target is the first scene
  or no such snapshot exists yet.
- `invalidate_snapshots_from(session, story_id, from_position) -> int`:
  deletes every snapshot in the story whose `through_scene_id` scene has
  `position >= from_position`; returns the count deleted. This is the "must
  delete or replace its snapshot and regenerate snapshots for all later
  scenes" step from `docs/data-model-v2.md`'s Continuity snapshot section —
  deletion only; regeneration (which needs an LLM call) is a `scene.agent`
  responsibility in the next encounter.
- `delete_snapshot(session, story_id, through_scene_id) -> bool`.

Out of scope: any LLM/continuity-editor call, or wiring `set_active_rendering`
/generation flows to call this module — that begins in
`e008-continuity-snapshot-agent`.

## Rationale

Mirrors this campaign's story-path core encounter
(`e002-story-field-rename-core`): the shared service layer between `cli` and
`agent` must exist, with its invariants enforced, before either consumer is
touched. Keeping snapshot *invalidation* (a pure data operation — delete
stale rows) in `core`, separate from snapshot *regeneration* (which requires
calling a model), lets `core` stay dependency-free of the LLM runtime, the
same separation `scene.core` already keeps from `scene.agent` everywhere
else in this codebase.

## Plan

1. Create `src/scene/core/continuity_snapshot.py` importing `ContinuitySnapshot`
   from `scene.data.continuity_snapshot`, `Scene` from `scene.data.scene`,
   and implementing the five functions above using the same `Session`-based
   CRUD style as `src/scene/core/rendering.py` and the same cross-entity
   validation style as `src/scene/core/scene_character.py`.
2. For `get_preceding_snapshot`, query `Scene` rows for `story_id` ordered by
   `position`, find the target scene's position, then look up a snapshot
   whose `through_scene_id` is the closest earlier scene that has one
   (walking backward from the immediately preceding scene, in case not every
   earlier scene has a snapshot — e.g. after a partial invalidation).
3. Add `test/scene/core/test_continuity_snapshot.py` covering: create/get/
   delete; the cross-story `ValueError`; the duplicate-pair `ValueError`;
   `get_preceding_snapshot` returning `None` for the first scene, returning
   the immediately preceding scene's snapshot when present, and walking
   backward past a scene with no snapshot; and `invalidate_snapshots_from`
   deleting the expected rows and returning the correct count.
4. Run `pdm run lint` and fix any findings.

## Verification

- `pdm run pytest` passes, including the new
  `test/scene/core/test_continuity_snapshot.py`.
- `pdm run lint` reports no findings.

## Log

### Review - 2026-08-24T18:13:46Z - John Hoff

Reviewed against the two applicable lore items (linting, unit-testing), both of which the Plan and Verification sections explicitly satisfy: pdm run lint is run to zero findings, and test/scene/core/test_continuity_snapshot.py is added mirroring the source path with concrete coverage for create/get/delete, both ValueError cases, get_preceding_snapshot's edge cases, and invalidate_snapshots_from's deletion/count behavior. Cross-checked the Requirements against the actually-landed ContinuitySnapshot model from e006 and against docs/data-model-v2.md / docs/prompt-guidance.md, which the Plan cites -- the described "at most one snapshot" invariant, the delete-only invalidation scope (regeneration correctly deferred to e008-continuity-snapshot-agent), and the "snapshot through the immediately preceding scene" semantics all match the docs, and the CRUD/validation style faithfully mirrors the cited rendering.py/scene_character.py/scene.py patterns already in src/scene/core. No lore conflicts found; PASS-WITH-NOTES.

### Completed - 2026-08-24T18:17:35Z - John Hoff

Continuity snapshot core service layer implemented as planned: src/scene/core/continuity_snapshot.py with create_snapshot (raising ValueError for a missing/cross-story scene or a duplicate (story_id, through_scene_id) pair), get_snapshot, get_preceding_snapshot (walks backward through earlier scenes by position to skip gaps left by partial invalidation), invalidate_snapshots_from (position-based cutoff, delete-only, returns the count deleted), and delete_snapshot -- all following the CRUD/ValueError conventions in rendering.py/scene_character.py/scene.py. Added test/scene/core/test_continuity_snapshot.py with 14 tests covering every function including both ValueError paths, the backward-walk gap case, and the invalidation count/no-op cases.

test/scene/core/** is fully green (77 passed) and pdm run lint is clean. Full repo suite: 436 passed, 0 failed (up from 422 before this encounter). Next: e008-continuity-snapshot-agent.
