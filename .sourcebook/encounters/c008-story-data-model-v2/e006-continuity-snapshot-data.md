---
archived: false
campaign: c008-story-data-model-v2
created_by: John Hoff
created_on: '2026-08-24T14:25:57Z'
depends_on:
- e005-story-field-rename-gui
kind: scripted
name: e006-continuity-snapshot-data
regions:
- data
status: draft
updated_by: John Hoff
updated_on: '2026-08-24T14:25:57Z'
---

# Continuity snapshot — data layer

## Requirements

Implement the `continuity_snapshot` table from `docs/data-model-v2.md` at the
ORM/schema level, the first encounter of this campaign's "generation path"
(the second of the two tracks agreed with the user, run only after the
entire "story path" — `e001`–`e005` — is complete and stable):

- New `src/scene/data/continuity_snapshot.py` module, `ContinuitySnapshot`
  ORM class mapped to table `continuity_snapshot`, following the exact
  columns/constraints/indexes in `docs/data-model-v2.md`'s "Continuity
  snapshot" section: `id` PK, `story_id` FK to `story.id` (`ON DELETE
  CASCADE`), `through_scene_id` FK to `scene.id` (`ON DELETE CASCADE`),
  `narrative_state` (`TEXT NOT NULL`, non-blank check), a `UNIQUE
  (story_id, through_scene_id)` constraint, and an index on
  `(story_id, through_scene_id)`.
- No migration path or backward compatibility is required (same destructive-
  change allowance as `e001-story-field-rename-data`).

Out of scope: any `scene.core`, `scene.agent`, `scene.cli`, or `scene.gui`
code that creates, reads, invalidates, or regenerates snapshots — those are
the next four encounters in this campaign, in that order.

## Rationale

`docs/data-model-v2.md` describes `continuity_snapshot` as a new entity, not
a modification of any existing table, so it can be added independently of
the story-path rename this campaign already completed. Landing it as its own
data-layer encounter — mirroring `e001`'s shape — keeps the "generation
path" following the same data → core → agent → cli → gui sequence the user
asked for, so every layer above it again builds against an already-correct,
stable schema.

## Plan

1. Create `src/scene/data/continuity_snapshot.py` with the `ContinuitySnapshot`
   class: `id: Mapped[int]` PK/autoincrement; `story_id: Mapped[int]` FK to
   `story.id` (`ondelete="CASCADE"`); `through_scene_id: Mapped[int]` FK to
   `scene.id` (`ondelete="CASCADE"`); `narrative_state: Mapped[str]`
   (`nullable=False`); a `CheckConstraint` on
   `length(trim(narrative_state)) > 0` (name
   `ck_continuity_snapshot_narrative_state_not_blank`, following the naming
   convention in `src/scene/data/story.py`/`scene.py`); a
   `UniqueConstraint("story_id", "through_scene_id", name=
   "uq_continuity_snapshot_story_id_through_scene_id")`; and an
   `Index("idx_continuity_snapshot_story_id_through_scene_id", "story_id",
   "through_scene_id")` (following the `Index` pattern in
   `src/scene/data/character.py`).
2. Delete the local `data/scene.db` (if present) so it is recreated with the
   new table on next use.
3. Add `test/scene/data/test_continuity_snapshot.py`, mirroring the shape of
   `test/scene/data/test_rendering.py`: creating a snapshot, the non-blank
   `narrative_state` check firing, the `(story_id, through_scene_id)`
   uniqueness constraint firing on a duplicate, and cascade deletes from both
   `story` and `scene`.
4. Run `pdm run lint` and fix any findings.

## Verification

- `pdm run pytest` passes, including the new
  `test/scene/data/test_continuity_snapshot.py`.
- `pdm run lint` reports no findings.
- Confirm `e001`–`e005` (the story-path encounters) are all `completed`
  before this encounter is opened.
