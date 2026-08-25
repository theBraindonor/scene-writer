---
archived: false
campaign: c008-story-data-model-v2
created_by: John Hoff
created_on: '2026-08-24T14:26:47Z'
depends_on:
- e007-continuity-snapshot-core
kind: scripted
name: e008-continuity-snapshot-agent
regions:
- agent
status: completed
updated_by: John Hoff
updated_on: '2026-08-24T18:48:57Z'
---

# Continuity snapshot — agent layer

## Requirements

Implement the prompt architecture from `docs/prompt-guidance.md` on top of
`e007-continuity-snapshot-core`: a continuity-editor role that turns an
accepted rendering into a new `continuity_snapshot`, and a reworked
scene-writer prompt that uses the preceding snapshot as compact continuity
context instead of every prior scene's full text.

- Add `AgentRole.CONTINUITY_EDITING = "SCENE_CONTINUITY_AGENT"` to
  `src/scene/agent/role.py`, following the existing `COORDINATING`/
  `RENDERING` members. This selector env var name is fixed by the user's
  already-populated `.env` — do not use any other spelling (e.g. not
  `SCENE_CONTINUITY_EDITING_AGENT`). Document the selector env var in
  `.env.example` and mention the new role in `models.example.yaml`'s
  comment block, the same way the existing two roles are documented.
- Add `src/scene/agent/continuity.py`:
  - `build_continuity_messages(session, story_id, scene_id) ->
    list[dict[str, Any]]`: builds the continuity-editor prompt from the
    "Continuity-editor prompt template" in `docs/prompt-guidance.md` — prior
    narrative state (via `core.continuity_snapshot.get_preceding_snapshot`,
    or a suitable "no prior state" placeholder for the first scene) and the
    newly accepted scene's active rendering body. Raise `ValueError` if the
    scene has no active rendering.
  - `run_continuity_edit(config, messages) -> str`: calls
    `scene.agent.llm.complete` (non-streaming — the continuity editor
    returns a single text block per `docs/prompt-guidance.md`, not prose to
    stream) and returns the response content.
  - `accept_scene(config, session, story_id, scene_id) ->
    ContinuitySnapshot`: orchestrates building the continuity messages,
    running the edit, and persisting the result via
    `core.continuity_snapshot.create_snapshot` (replacing an existing
    snapshot for that scene first, if present, since the "at most one"
    invariant is enforced at the `core` layer). This is the single entry
    point CLI/GUI callers use after a rendering is accepted as active.
  - `regenerate_snapshots_from(config, session, story_id, from_position) ->
    None`: calls `core.continuity_snapshot.invalidate_snapshots_from`, then
    walks the story's scenes from `from_position` forward in order, calling
    `accept_scene` for each scene that has an active rendering (stopping at
    the first scene in that range with no active rendering, since a
    snapshot cannot be produced without one) — the "Regenerate snapshots
    from Scene N forward using active renderings" step from
    `docs/prompt-guidance.md`'s revision-and-invalidation flow.
- Rework `build_render_messages` in `src/scene/agent/rendering.py` to follow
  `docs/prompt-guidance.md`'s "Scene-writing prompt template": the system
  message carries the stable story reference (`story_brief`,
  `style_guidance`, `generation_guideance`, character/location cards
  rendered as the compact prose cards the guidance document shows, not raw
  rows) plus the fixed writer instructions; a `CURRENT CANON` section holds
  the preceding scene's `narrative_state` (via `get_preceding_snapshot`),
  omitted when there is none; an `OPTIONAL RECENT PROSE` section includes
  only the immediately preceding scene's active rendering body, when one
  exists (`docs/prompt-guidance.md`: "Include the preceding active
  rendering only when exact voice ... needs to carry directly into the next
  scene" — including it unconditionally for the immediately preceding scene
  is the simplest reading that still satisfies this without deferring to a
  configurable policy this campaign doesn't need); the final user message is
  the current scene's brief (heading, POV, brief, required actions, desired
  outcome, target length), replacing the old per-prior-scene
  user/assistant message pairs entirely.

Out of scope: any CLI/GUI wiring that calls `accept_scene` after a
generation, or a "regenerate forward" trigger on version activation — those
are `e009-continuity-snapshot-cli` and `e010-continuity-snapshot-gui`.

## Rationale

This is where `docs/prompt-guidance.md`'s two-model split ("a scene-writing
model" and "a continuity-editor model", "may be the same model or two
different models") actually lands in code: `AgentRole` already exists as
exactly this kind of per-responsibility model selector
(`src/scene/agent/role.py`, `src/scene/agent/config.py`), so a third role is
the natural extension rather than a new mechanism. The selector env var name
(`SCENE_CONTINUITY_AGENT`) is fixed by what the user has already configured
in their local `.env`, ahead of this encounter's implementation — the code
must match that name exactly rather than the plausible-but-wrong
`SCENE_CONTINUITY_EDITING_AGENT` an earlier draft of this plan used.
Reworking `build_render_messages` here — rather than leaving the
full-history strategy in place until `cli`/`gui` also change — keeps the
prompt-construction change (`scene.agent`'s responsibility) and the "when
does the app call the continuity editor" change (`cli`/`gui`'s
responsibility) in separate, independently reviewable encounters, matching
how the story-path track separated "what fields exist in a prompt" (`e003`)
from "when the app calls the coordinator/renderer" (already existing before
this campaign).

## Plan

1. `src/scene/agent/role.py`: add the `CONTINUITY_EDITING` member with value
   `"SCENE_CONTINUITY_AGENT"`.
2. `.env.example` / `models.example.yaml`: document `SCENE_CONTINUITY_AGENT`
   alongside the existing two selector env vars.
3. Create `src/scene/agent/continuity.py` implementing
   `build_continuity_messages`, `run_continuity_edit`, `accept_scene`, and
   `regenerate_snapshots_from` as described above.
4. Rework `build_render_messages` (and its helpers `_scene_detail_text`,
   `_character_roster_markdown`, `_location_roster_markdown`) in
   `src/scene/agent/rendering.py` per the new template; render only the
   characters/locations assigned to the target scene (via
   `list_characters_for_scene`/`list_locations_for_scene`, already imported)
   as compact cards, per `docs/prompt-guidance.md`'s "Use compact prose
   cards" section, rather than the full story roster.
5. Add `test/scene/agent/test_continuity.py` covering
   `build_continuity_messages` (including the no-prior-state and
   no-active-rendering cases), `accept_scene` (including replacing an
   existing snapshot), and `regenerate_snapshots_from` (invalidation +
   forward walk, stopping at an unrendered scene).
6. Update `test/scene/agent/test_rendering.py` for the reworked
   `build_render_messages` output shape, and `test/scene/agent/test_role.py`
   for the new `AgentRole` member (asserting `env_var ==
   "SCENE_CONTINUITY_AGENT"`).
7. Run `pdm run lint` and fix any findings.

## Verification

- `pdm run pytest` passes, including the new `test/scene/agent/test_continuity.py`
  and the updated `test/scene/agent/test_rendering.py` and
  `test/scene/agent/test_role.py`.
- `pdm run lint` reports no findings.
- Grep confirms `AgentRole.CONTINUITY_EDITING` resolves to
  `"SCENE_CONTINUITY_AGENT"` (not `SCENE_CONTINUITY_EDITING_AGENT`) in
  `src/scene/agent/role.py`, and that `.env.example` documents the same
  name.
- Manually inspect `build_render_messages`' output for a multi-scene story
  fixture (e.g. via a quick REPL/script call) and confirm it no longer
  includes every prior scene's full rendering as separate messages.

## Log

### Review - 2026-08-24T18:25:34Z - John Hoff

Reviewed e008-continuity-snapshot-agent against the world's linting and unit-testing lore (the only applicable lore resolved for the agent region) -- both are satisfied via explicit pdm run lint/pdm run pytest steps and correctly-mirrored new/updated test files. Cross-checked the Plan's claimed dependencies against the actual landed code: src/scene/core/continuity_snapshot.py (e007) signatures and the "at most one snapshot" duplicate-raise behavior match what accept_scene assumes; src/scene/agent/role.py's existing COORDINATING/RENDERING pattern supports the proposed CONTINUITY_EDITING member; and the current src/scene/agent/rendering.py confirms the full-history problem the rework addresses and the existing helper names/imports the Plan builds on. Verified the previously-corrected env var name is now fully consistent: SCENE_CONTINUITY_AGENT is used everywhere it's asserted as the actual value (Requirements, Rationale, Plan steps 1/2/6), and the old SCENE_CONTINUITY_EDITING_AGENT appears only as explicit cautionary negative examples, not as a leftover mistake. One minor, non-blocking gap: the reworked compact character/location card format is grounded in docs/prompt-guidance.md's example but not spelled out as a literal template the way the scene-writing prompt template was. Overall the encounter is well-grounded and reviewable -- PASS-WITH-NOTES.

### Completed - 2026-08-24T18:48:57Z - John Hoff

Continuity-editor role and prompt rework implemented as planned:

- src/scene/agent/role.py: added AgentRole.CONTINUITY_EDITING = "SCENE_CONTINUITY_AGENT" (matching the user's already-configured .env, confirmed by grep).
- .env.example / models.example.yaml: documented SCENE_CONTINUITY_AGENT alongside the existing two selector env vars.
- New src/scene/agent/continuity.py: build_continuity_messages (continuity-editor prompt template, no-prior-state placeholder for the first scene, raises ValueError with no active rendering), run_continuity_edit (non-streaming complete()), accept_scene (deletes any existing snapshot first, then create_snapshot -- satisfying core's "at most one" invariant), and regenerate_snapshots_from (invalidate then walk forward, stopping at the first unrendered scene in range).
- Reworked src/scene/agent/rendering.py's build_render_messages per the Scene-writing prompt template: system message now carries story_brief/style_guidance/generation_guideance plus compact CHARACTER:/LOCATION: cards scoped to only the target scene's assigned entities (not the full story roster); the single user message now holds an optional CURRENT CANON section (via get_preceding_snapshot), an optional OPTIONAL RECENT PROSE section (immediately preceding scene's active rendering, when present -- no longer required, no longer raises if absent), and a SCENE BRIEF section (Heading/Point of view/Brief/Required actions/Desired outcome/Target length, omitting absent optional fields). The old per-prior-scene user/assistant message loop is gone -- confirmed via a manual REPL run that a 2-scene story now produces exactly 2 messages instead of one pair per prior scene.

Added test/scene/agent/test_continuity.py (9 tests) and substantially reworked test/scene/agent/test_rendering.py's build_render_messages coverage for the new message shape (including a test that a prior scene lacking an active rendering no longer raises); added a CONTINUITY_EDITING case to test_role.py.

test/scene/agent/** is fully green (144 passed) and pdm run lint is clean. Full repo suite: 444 passed, 0 failed (up from 436 before this encounter). Next: e009-continuity-snapshot-cli.
