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
status: draft
updated_by: John Hoff
updated_on: '2026-08-24T14:26:48Z'
---

# Continuity snapshot — agent layer

## Requirements

Implement the prompt architecture from `docs/prompt-guidance.md` on top of
`e007-continuity-snapshot-core`: a continuity-editor role that turns an
accepted rendering into a new `continuity_snapshot`, and a reworked
scene-writer prompt that uses the preceding snapshot as compact continuity
context instead of every prior scene's full text.

- Add `AgentRole.CONTINUITY_EDITING = "SCENE_CONTINUITY_EDITING_AGENT"` to
  `src/scene/agent/role.py`, following the existing `COORDINATING`/
  `RENDERING` members; document the new selector env var in `.env.example`
  and mention the new role in `models.example.yaml`'s comment block, the
  same way the existing two roles are documented.
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
the natural extension rather than a new mechanism. Reworking
`build_render_messages` here — rather than leaving the full-history strategy
in place until `cli`/`gui` also change — keeps the prompt-construction
change (`scene.agent`'s responsibility) and the "when does the app call the
continuity editor" change (`cli`/`gui`'s responsibility) in separate,
independently reviewable encounters, matching how the story-path track
separated "what fields exist in a prompt" (`e003`) from "when the app calls
the coordinator/renderer" (already existing before this campaign).

## Plan

1. `src/scene/agent/role.py`: add the `CONTINUITY_EDITING` member.
2. `.env.example` / `models.example.yaml`: document `SCENE_CONTINUITY_EDITING_AGENT`
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
   for the new `AgentRole` member.
7. Run `pdm run lint` and fix any findings.

## Verification

- `pdm run pytest` passes, including the new `test/scene/agent/test_continuity.py`
  and the updated `test/scene/agent/test_rendering.py` and
  `test/scene/agent/test_role.py`.
- `pdm run lint` reports no findings.
- Manually inspect `build_render_messages`' output for a multi-scene story
  fixture (e.g. via a quick REPL/script call) and confirm it no longer
  includes every prior scene's full rendering as separate messages.
