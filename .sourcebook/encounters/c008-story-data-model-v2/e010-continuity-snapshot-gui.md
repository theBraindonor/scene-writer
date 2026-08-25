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
status: completed
updated_by: John Hoff
updated_on: '2026-08-25T02:30:05Z'
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
  - Restructure the display area into two tabs via a `QTabWidget` (matching
    the existing tab pattern in `src/scene/gui/entity_column/column.py`),
    since the user wants prose and continuity state visually separated
    rather than stacked: a "Prose" tab holding the existing `body_view`, and
    a new "Continuity Snapshot" tab holding a read-only `QPlainTextEdit`
    showing the current scene's snapshot text (via
    `core.continuity_snapshot.get_snapshot(session, story_id, scene_id)`,
    since the panel is about *this* scene's resulting state, not the input
    `get_preceding_snapshot` uses) or a placeholder when none exists yet.
    The Versions list/buttons and the Generate/Cancel row stay *outside*
    the tab widget (they act on the whole scene, not on whichever tab is
    active) — only `body_view`'s display swaps with the tab selection,
    since the continuity snapshot is a property of the scene, not of
    whichever rendering version happens to be selected in the Versions
    list, so it doesn't change as the user browses older versions.
    Refresh the Continuity Snapshot tab in `_refresh()` and after
    `accept_scene`/`regenerate_snapshots_from` complete.

Out of scope: any change to `entity_column/*` or `story_header.py`; a
dedicated cross-scene snapshot browser (the design doc's snapshot review
step is "may show ... for review," not a requirement, and the per-scene tab
above already satisfies "review the resulting canon" for the scene
currently selected).

## Rationale

`docs/prompt-guidance.md` explicitly calls out that the application "may
show the resulting snapshot to the user for review before it is used as
canon," and this project's GUI is the intended long-term "unified GUI"
surface per the world summary — so surfacing the snapshot, not just silently
persisting it, is worth the addition here even though `e009` didn't need an
equivalent for the TUI (which is already fully text-oriented and shows the
raw rendering body next to version selection; `e011` later added an
equivalent panel to the TUI on the user's request, stacked below the output
pane rather than tabbed, since the TUI has no existing tab widget precedent
to match). The GUI does have that precedent (`entity_column/column.py`'s
`QTabWidget`), and the user specifically asked for two tabs — prose and
continuity snapshot — rather than a stacked panel, so this encounter follows
that established Qt pattern instead of porting `e011`'s CLI layout verbatim.
Otherwise this encounter is a straight port of `e009`'s wiring into
`rendering_column.py`/`main_window.py`, following the porting relationship
already documented in `RenderingColumn`'s own docstring.

## Plan

1. `src/scene/gui/main_window.py`: resolve and pass through the
   `CONTINUITY_EDITING` config into `RenderingColumn`.
2. `src/scene/gui/rendering_column.py`:
   - Add the `continuity_config` parameter; wire `accept_scene` into
     `_on_generation_finished` and `regenerate_snapshots_from` into
     `_on_activate_clicked`.
   - Add `self.continuity_snapshot_view = QPlainTextEdit()`
     (`setReadOnly(True)`, following the existing `body_view`/prompt-preview
     read-only pattern).
   - Replace `content_layout.addWidget(self.body_view)` with a
     `self.tabs = QTabWidget()` holding `self.body_view` under a "Prose" tab
     and `self.continuity_snapshot_view` under a "Continuity Snapshot" tab;
     `content_layout.addWidget(self.tabs)` in `body_view`'s old position
     (i.e. still between `version_row` and `generate_row`).
   - Add a `_refresh_continuity_snapshot()` helper (mirroring
     `e011`'s CLI helper of the same purpose) that queries
     `core.continuity_snapshot.get_snapshot` for `current_scene_id` and
     updates `continuity_snapshot_view`, or shows a placeholder when there's
     no scene selected or no snapshot yet; call it from `_refresh()`, from
     the end of `_on_generation_finished`, and after
     `regenerate_snapshots_from` completes in `_on_activate_clicked`.
3. Update `test/scene/gui/test_main_window.py` for the additional config
   resolution, and `test/scene/gui/test_rendering_column.py` for the new
   parameter, the tab restructuring (`body_view`/`continuity_snapshot_view`
   both still queryable, now as tab pages), the two call sites (stubbed,
   consistent with how this file already stubs `stream_render`/worker
   behavior), and the snapshot tab's display/refresh behavior.
4. Run `pdm run lint` and fix any findings.

## Verification

- `pdm run pytest` passes, including the updated
  `test/scene/gui/test_main_window.py` and
  `test/scene/gui/test_rendering_column.py`.
- `pdm run lint` reports no findings.
- Launch the GUI (per the project's `run` skill, if usable in this
  environment): confirm the rendering side shows "Prose"/"Continuity
  Snapshot" tabs; generate a rendering for a scene, confirm the Continuity
  Snapshot tab populates after generation; activate an older version and
  confirm later scenes' snapshots are regenerated (spot-check via
  `pdm run scene-data continuity-snapshot get`) while the Prose tab's
  content follows the selected version and the Continuity Snapshot tab
  does not change based on version selection.
- This is the final encounter in `c008-story-data-model-v2`; once it's
  `completed`, confirm every prompt-construction and schema change described
  in `docs/data-model-v2.md`/`docs/prompt-guidance.md` is reflected end to
  end before considering the campaign for completion.

## Log

### Review - 2026-08-24T20:28:31Z - John Hoff

Reviewed against this encounter's applicable lore (linting, unit-testing) -- both are explicitly satisfied: the Plan runs pdm run lint to a clean state and adds/updates mirrored tests in test/scene/gui/test_main_window.py and test/scene/gui/test_rendering_column.py, with pdm run pytest passing required for completion. The tab-restructuring is accurately grounded in the current code: the QTabWidget precedent cited from entity_column/column.py is real, and every rendering_column.py symbol the Plan touches (body_view, content_layout, version_row/generate_row ordering, _refresh, _on_generation_finished, _on_activate_clicked) matches what's actually there today. It is also internally coherent on the key scoping question: refresh of the new Continuity Snapshot tab is wired only to _refresh(), post-generation, and post-regeneration -- never to Versions-list browsing (_on_version_selected) -- correctly keeping the snapshot scene-scoped rather than version-scoped, matching its own stated rationale. Two non-blocking notes for implementation: (1) _on_activate_clicked's plan to resolve the scene position "via get_scene" is redundant with the column's already-tracked current_scene_position; (2) accept_scene/regenerate_snapshots_from are wired to run synchronously on the GUI thread rather than through the existing QThread worker pattern used for rendering generation, which could block the UI during regenerate_snapshots_from's multi-scene loop -- worth a look during implementation even though it mirrors the already-accepted e009 CLI approach. Verdict: PASS-WITH-NOTES.

### Message - 2026-08-24T20:37:29Z - John Hoff

Implementation notes / minor deviations from the literal Plan text, both consistent with the reviewer's PASS-WITH-NOTES feedback and the campaign's established "continuity is optional, never blocks core rendering" principle (e009/e011):

1. _on_activate_clicked resolves the activated rendering's scene position via the already-tracked self.current_scene_position rather than a fresh get_scene call, per the reviewer's note.
2. accept_scene/regenerate_snapshots_from run on a new background QThread (_ContinuityWorker, mirroring _RenderWorker's pattern) rather than synchronously on the GUI thread, per the reviewer's note -- avoids blocking the UI during a multi-scene regenerate_snapshots_from chain.
3. Went beyond the Plan's literal "folds a continuity-resolution error into the existing error notice if both are present": main_window.py does combine both error strings into one notice (as planned), but rendering_column.py's generate_button is now disabled only when the rendering llm_config itself is missing, not when only continuity_config failed to resolve -- otherwise a missing/misconfigured SCENE_CONTINUITY_AGENT would block scene generation entirely, contradicting continuity's optional status established throughout e008-e011.

test/scene/gui/** is fully green (105 passed) and pdm run lint is clean. Full repo suite: 471 passed, 0 failed (up from 460 before this encounter).

### Completed - 2026-08-25T02:30:05Z - John Hoff

Confirmed working by the user live in the GUI: Prose/Continuity Snapshot tabs display correctly, the snapshot tab populates after generation, and updates correctly after activating an older version while the Prose tab follows version selection. This closes out this campaign's generation-path track (e006-e010) and the token-budget/streaming-display/CLI-panel follow-up (e011). Campaign c008-story-data-model-v2 stays open at the user's request -- they want further GUI experience changes before closing it out.
