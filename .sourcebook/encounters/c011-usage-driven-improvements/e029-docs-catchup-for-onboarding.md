---
archived: false
campaign: c011-usage-driven-improvements
created_by: John Hoff
created_on: '2026-08-31T23:49:56Z'
depends_on: []
kind: scripted
name: e029-docs-catchup-for-onboarding
regions:
- agent
- cli
- data
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-09-01T00:02:36Z'
---

## Requirements

- Consolidate `docs/data-model.md` and `docs/data-model-v2.md` into a single data-model
  document reflecting the schema as currently implemented (the v2 schema). Retire the
  v1-vs-v2 diff framing — there is only one current model now, not two documents to
  reconcile.
- Review `docs/prompt-guidance.md` end-to-end against the current `scene.agent`
  implementation (construction phase, drafting phase, continuity-snapshot handling) and
  correct any part that has drifted from implementation reality.
- Leave `docs/application-agent.md` as-is — already reviewed and confirmed up to date by
  the user.
- Update `README.md` so it: (a) references the consolidated data-model doc and
  `docs/prompt-guidance.md`/`docs/application-agent.md` appropriately instead of the
  retired v1/v2 pair, and (b) promotes the `scene-writer` GUI console script as the
  standard way to use the application, rather than presenting the individual CLI programs
  (`scene-coordinator`, `scene-data`, etc.) as the primary interface. CLI programs remain
  documented (e.g. `scene-data` for direct data admin), but framed as secondary to
  `scene-writer` for standard usage.

## Rationale

A second person is now ready to try the application out, which is the first time these
docs will be read by someone other than the primary developer. That onboarding need
surfaced two concrete problems while reviewing what to point them at:

1. `docs/data-model.md` and `docs/data-model-v2.md` currently coexist as two separate
   files, with `data-model-v2.md` framed as a diff against `data-model.md` (a `v1 -> v2`
   rename/addition table). Since v2 is what's actually implemented, handing a newcomer
   both files (or just the stale v1 one, which `README.md` currently links to) is
   confusing rather than helpful.
2. `README.md` still frames the standalone CLI programs as the primary interface
   ("The project ships as a collection of standalone CLI programs... alongside a unified
   `scene-writer` desktop GUI"), when in practice `scene-writer` is what should be
   recommended for standard usage now that it exists and wraps the same coordinating/
   rendering agents.

This is purely a documentation-accuracy pass ahead of that onboarding — no source code
changes are in scope.

## Plan

1. Read `docs/data-model.md` and `docs/data-model-v2.md` in full, and diff the v2 schema
   there against the actual SQLAlchemy models in `src/scene/data` to confirm v2 (not some
   further-drifted state) is in fact current.
2. Merge them into a single `docs/data-model.md`: keep the v2 schema as the sole
   documented model (entities, columns, constraints, indexes, ER diagram), drop the
   "what changed from v1" table and v1-only framing, and delete `docs/data-model-v2.md`.
3. Read `docs/prompt-guidance.md` in full alongside `src/scene/agent` (construction phase,
   drafting phase, continuity-snapshot generation/consumption) and correct any
   prompt-guidance detail that no longer matches the implementation (e.g. model role
   split, continuity snapshot persistence, workflow steps).
4. Update `README.md`:
   - Fix the "Data model" section's link/description to point at the consolidated
     `docs/data-model.md`.
   - Add references to `docs/prompt-guidance.md` and `docs/application-agent.md` where
     the README describes the generation pipeline / application agent, so a newcomer can
     find the deeper docs from the README.
   - Re-order/re-word the top-level description and "Development" walkthrough so
     `scene-writer` is presented as the standard way to run the application, with the
     individual CLI programs (`scene-coordinator`, `scene-data`) described as
     supporting/administrative tools rather than the primary interface.
5. Re-read all four docs plus `README.md` together for cross-reference consistency (no
   remaining links to the deleted `data-model-v2.md`, no remaining "CLI-first" framing
   that contradicts the `scene-writer`-first framing).

## Verification

- No source code under `src/` or `test/` changes as part of this encounter — confirm via
  `git status`/`git diff` that only `README.md` and files under `docs/` were touched, so
  the `linting`/`unit-testing` lore's ruff/pytest gates are not applicable here.
- `docs/data-model-v2.md` no longer exists, and no remaining file (including `README.md`)
  links to it.
- `docs/data-model.md` accurately reflects the current SQLAlchemy models in
  `src/scene/data` (spot-check column/entity names against the ORM).
- `docs/prompt-guidance.md` accurately reflects the current construction/drafting/
  continuity-snapshot implementation in `src/scene/agent` (spot-check against the actual
  prompt-building code).
- `README.md` presents `scene-writer` as the standard entry point and links out to the
  consolidated data-model doc, `docs/prompt-guidance.md`, and `docs/application-agent.md`.

## Log

### Review - 2026-08-31T23:56:03Z - John Hoff

Reviewed e029-docs-catchup-for-onboarding (scripted): the Plan correctly identifies that this is a docs-only pass and explicitly gates its Verification on confirming via git diff that no src/test files change, which properly satisfies (by correctly ruling out) the world's linting and unit-testing lore rather than ignoring them. The plan-then-cross-check structure (diff v2 schema against actual ORM models, check prompt-guidance against actual agent code, then a final cross-reference pass) is sound and traceable to the Requirements. One caveat noted but not chased: the encounter's assigned regions (agent/cli/data/gui) don't actually cover the files being touched (README.md, docs/), so if a docs/root region with its own lore exists outside this encounter's region list, it wouldn't have surfaced here — flagged as unverified rather than confirmed. No conflicts with lore found; approved to proceed.

### Message - 2026-09-01T00:01:27Z - John Hoff

Executed the plan. Confirmed via the actual SQLAlchemy models in src/scene/data that data-model-v2.md (not data-model.md) matched the implemented schema exactly; consolidated into a single docs/data-model.md dropping the v1-vs-v2 framing, and deleted docs/data-model-v2.md. Reviewed docs/prompt-guidance.md against src/scene/agent: found a real behavioral drift in the continuity-editor "Rules" list (doc said "preserve all prior facts unless changed"; the actual agent-prompts.yaml system prompt instead prunes/compresses for relevance and groups facts by theme) and corrected it, and added a note pointing to agent-prompts.yaml as the canonical source for exact prompt wording. Left docs/application-agent.md untouched. Updated README.md to lead with scene-writer as the standard interface, reordered the CLI tools as secondary/administrative, added a Further documentation section linking prompt-guidance.md and application-agent.md, and fixed a real inaccuracy: the README claimed the GUI chat panel reuses SCENE_COORDINATING_AGENT, but src/scene/gui/main_window.py:101 actually uses a distinct SCENE_APPLICATION_AGENT role — corrected the README to name all four agent roles (SCENE_APPLICATION_AGENT, SCENE_COORDINATING_AGENT, SCENE_RENDERING_AGENT, SCENE_CONTINUITY_AGENT) accurately. Verified via git status/diff that only README.md and docs/ files changed — no src/ or test/ changes, so linting/unit-testing lore gates don't apply.
