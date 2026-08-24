---
archived: false
campaign: c008-story-data-model-v2
created_by: John Hoff
created_on: '2026-08-24T14:27:55Z'
depends_on:
- e009-continuity-snapshot-cli
kind: scripted
name: e010-continuity-snapshot-gui
regions:
- gui
status: draft
updated_by: John Hoff
updated_on: '2026-08-24T14:27:56Z'
---

# Continuity snapshot — GUI layer

## Requirements

Port `e009-continuity-snapshot-cli`'s wiring into the Qt GUI, the last
encounter in this campaign:

- `src/scene/gui/main_window.py`: additionally resolve
  `get_llm_config(AgentRole.CONTINUITY_EDITING)` using the same
  `try/except (RuntimeError, TypeError)` pattern already used for
  `AgentRole.RENDERING`; pass the resulting config (and its error, if any)
  into `RenderingColumn`.
- `src/scene/gui/rendering_column.py`:
  - `RenderingColumn.__init__` accepts an additional
    `continuity_config: LLMConfig | None` (and folds a continuity-resolution
    error into the existing `error` notice if both are present) and stores
    it.
  - `_on_generation_finished`: after `create_rendering`/`set_active_rendering`
    for a completed (non-empty) generation, call
    `scene.agent.continuity.accept_scene` with `continuity_config` when set;
    on failure, extend the existing notice (`GENERATION_ERROR_*`/
    `CANCELLED_*`/none) with a continuity-specific message rather than
    silently dropping the failure, following the same "always show *a*
    notice, never crash" posture the rest of this method already has.
  - `_on_activate_clicked`: after `set_active_rendering` for the selected
    (non-latest) version, call
    `scene.agent.continuity.regenerate_snapshots_from` with
    `continuity_config` when set (using `current_story_id` and the
    activated rendering's scene position, resolved via `get_scene`), the
    same "active rendering changed" trigger `e009` wires into
    `render_app.py`'s `_activate_selected_version`.
  - Add a read-only "Continuity Snapshot" panel to `content_widget` (a
    `QPlainTextEdit`, `setReadOnly(True)`, below `version_row` following the
    existing section layout) that shows the current scene's snapshot text
    (via `core.continuity_snapshot.get_snapshot(session, story_id,
    scene_id)`, since the panel is about *this* scene's resulting state, not
    the input `get_preceding_snapshot` uses) or a placeholder when none
    exists yet; refresh it in `_refresh()` and after `accept_scene`/
    `regenerate_snapshots_from` complete.

Out of scope: any change to `entity_column/*` or `story_header.py`; a
dedicated cross-scene snapshot browser (the design doc's snapshot review
step is "may show ... for review," not a requirement, and the read-only
panel above already satisfies "review the resulting canon" for the scene
currently selected).

## Rationale

`docs/prompt-guidance.md` explicitly calls out that the application "may
show the resulting snapshot to the user for review before it is used as
canon," and this project's GUI is the intended long-term "unified GUI"
surface per the world summary — so surfacing the snapshot, not just silently
persisting it, is worth the small addition here even though `e009` didn't
need an equivalent for the TUI (which is already fully text-oriented and
shows the raw rendering body next to version selection). Otherwise this
encounter is a straight port of `e009`'s wiring into
`rendering_column.py`/`main_window.py`, following the porting relationship
already documented in `RenderingColumn`'s own docstring.

## Plan

1. `src/scene/gui/main_window.py`: resolve and pass through the
   `CONTINUITY_EDITING` config into `RenderingColumn`.
2. `src/scene/gui/rendering_column.py`: add the `continuity_config`
   parameter; wire `accept_scene` into `_on_generation_finished` and
   `regenerate_snapshots_from` into `_on_activate_clicked`; add the
   read-only snapshot panel and its refresh logic.
3. Update `test/scene/gui/test_main_window.py` for the additional config
   resolution, and `test/scene/gui/test_rendering_column.py` for the new
   parameter, the two call sites (stubbed, consistent with how this file
   already stubs `stream_render`/worker behavior), and the snapshot panel's
   display/refresh behavior.
4. Run `pdm run lint` and fix any findings.

## Verification

- `pdm run pytest` passes, including the updated
  `test/scene/gui/test_main_window.py` and
  `test/scene/gui/test_rendering_column.py`.
- `pdm run lint` reports no findings.
- Launch the GUI (per the project's `run` skill, if usable in this
  environment): generate a rendering for a scene, confirm the Continuity
  Snapshot panel populates after generation; activate an older version and
  confirm later scenes' snapshots are regenerated (spot-check via
  `pdm run scene-data continuity-snapshot get`).
- This is the final encounter in `c008-story-data-model-v2`; once it's
  `completed`, confirm every prompt-construction and schema change described
  in `docs/data-model-v2.md`/`docs/prompt-guidance.md` is reflected end to
  end before considering the campaign for completion.
