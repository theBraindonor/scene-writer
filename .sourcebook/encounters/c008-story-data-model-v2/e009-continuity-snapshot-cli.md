---
archived: false
campaign: c008-story-data-model-v2
created_by: John Hoff
created_on: '2026-08-24T14:27:31Z'
depends_on:
- e008-continuity-snapshot-agent
kind: scripted
name: e009-continuity-snapshot-cli
regions:
- cli
status: completed
updated_by: John Hoff
updated_on: '2026-08-24T19:12:08Z'
---

# Continuity snapshot — CLI layer

## Requirements

Wire `e008-continuity-snapshot-agent`'s `accept_scene`/`regenerate_snapshots_from`
into the CLI-driven rendering flow, and expose read/delete access to
snapshots via `scene-data`:

- `src/scene/cli/coordinator.py`: the `render` command additionally resolves
  `get_llm_config(AgentRole.CONTINUITY_EDITING)`, using the same
  `try/except (RuntimeError, TypeError)` pattern already used for
  `AgentRole.RENDERING`; pass the resulting config (which may be `None` if
  unresolved) into `RenderApp`.
- `src/scene/cli/render_app.py`:
  - `RenderApp.__init__` accepts an additional `continuity_config:
    LLMConfig | None` and stores it (mirroring the existing `config`
    parameter), threaded down to `RenderScreen`.
  - After `_render_scene` persists a new rendering and calls
    `set_active_rendering` (i.e. a fresh generation is immediately accepted
    as canon, matching this app's existing behavior of always activating
    what it just generated), call `scene.agent.continuity.accept_scene`
    with `continuity_config` when it is not `None`; on failure (missing
    config, or the call raising), show a notice rather than crashing the TUI
    — following the existing `_show_cancelled_notice`-style notice pattern.
  - After `_activate_selected_version` sets a different rendering active for
    a scene, call `scene.agent.continuity.regenerate_snapshots_from` with
    that scene's `story_id`/`position` (via `get_scene`) when
    `continuity_config` is set, since activating a non-latest version is
    exactly the "active rendering changed for Scene N" case
    `docs/prompt-guidance.md`'s revision-and-invalidation flow describes.
- `src/scene/cli/data.py`: add a `continuity-snapshot` Typer sub-app
  (`scene-data continuity-snapshot ...`), mirroring the `rendering_app`
  group's style: `get <story_id> <through_scene_id>` (echoes
  `narrative_state`, or a not-found message + exit code 1) and `delete
  <story_id> <through_scene_id>`. No manual `create`/`update` commands —
  snapshot content is always LLM-generated via `accept_scene`, never
  hand-authored, unlike every other entity this file manages.

Out of scope: `coordinator_app.py` (the coordinating-chat TUI doesn't
generate renderings, so it has no accept/regenerate trigger to wire); GUI
wiring (`e010-continuity-snapshot-gui`).

## Rationale

`render_app.py` (`scene-render`) is the CLI-driven reference implementation
of the rendering workflow — `src/scene/gui/rendering_column.py`'s own
docstring calls it "the reference implementation this column ports into
Qt" — so wiring the continuity-editor call here first, before
`e010-continuity-snapshot-gui` ports the same wiring into Qt, keeps this
campaign's data → core → agent → cli → gui ordering intact for the
generation path exactly as it did for the story-fields path.

## Plan

1. `src/scene/cli/coordinator.py`: resolve and pass through the
   `CONTINUITY_EDITING` config in the `render` command.
2. `src/scene/cli/render_app.py`: add the `continuity_config` parameter and
   the two call sites described above, each wrapped so a missing config or
   a call failure degrades to a notice instead of crashing generation or
   version activation.
3. `src/scene/cli/data.py`: add the `continuity-snapshot` Typer sub-app with
   `get`/`delete`, following the existing `rendering_app` command style
   (plain `typer.echo`, `typer.Exit(code=1)` on not-found).
4. Update `test/scene/cli/test_coordinator.py` for the additional config
   resolution in `render`; update `test/scene/cli/test_render_app.py` for
   the accept/regenerate call sites (mocking or stubbing the continuity
   calls, consistent with how existing tests in this file stub
   `stream_render`/LLM calls); add continuity-snapshot command coverage to
   `test/scene/cli/test_data.py`.
5. Run `pdm run lint` and fix any findings.

## Verification

- `pdm run pytest` passes, including the updated
  `test/scene/cli/test_coordinator.py`, `test/scene/cli/test_render_app.py`,
  and `test/scene/cli/test_data.py`.
- `pdm run lint` reports no findings.
- `pdm run scene-data continuity-snapshot --help` shows the new `get`/
  `delete` commands.

## Log

### Review - 2026-08-24T18:59:51Z - John Hoff

e009-continuity-snapshot-cli's Plan correctly honors both applicable lore items -- it schedules pdm run lint and full pdm run pytest coverage (with tests added at the correct mirrored test/scene/cli/... paths) as explicit steps and Verification gates -- and is well-grounded in the landed e008 agent surface (accept_scene/regenerate_snapshots_from signatures and the CONTINUITY_EDITING role/config resolution match exactly). Two notes for the implementer before this is scripted further: (1) the coordinator.py wiring asks to both "reuse the same try/except pattern" used for the required RENDERING config (which exits on failure) and to "pass the resulting config, which may be None" -- for the optional CONTINUITY_EDITING config the except branch should set the config to None rather than exit, and the Plan should say so explicitly rather than leaving the two instructions in tension; (2) the continuity-snapshot get CLI command's backing core-layer lookup by exact (story_id, scene_id) was not confirmed within this review's reading bounds (only delete_snapshot and get_preceding_snapshot, which has different semantics, were visible) and should be verified against scene/core/continuity_snapshot.py before implementation.

### Completed - 2026-08-24T19:12:08Z - John Hoff

CLI wiring implemented as planned, resolving both review notes:

- src/scene/cli/coordinator.py: render now additionally resolves AgentRole.CONTINUITY_EDITING, but as an optional dependency -- on RuntimeError/TypeError it prints "Continuing without it" and sets continuity_config=None rather than exiting, distinct from the required RENDERING resolution which still exits (resolving the review's note 1).
- src/scene/cli/render_app.py: RenderApp takes an additional continuity_config: LLMConfig | None = None; _render_scene calls accept_scene after a generation is saved+activated (try/except -> new #continuity-notice Static, never crashes); _activate_selected_version fires a new @work(thread=True) _regenerate_snapshots helper after activating a non-latest version (kept off the main event loop since _activate_selected_version itself runs as a plain asyncio worker, not a thread).
- src/scene/cli/data.py: new continuity-snapshot Typer sub-app with get/delete (backed by core.continuity_snapshot.get_snapshot/delete_snapshot from e007 -- resolving the review's note 2, which just fell outside that reviewer's bounded reading surface).

Updated test/scene/cli/test_coordinator.py (optional-config resolution/failure), test/scene/cli/test_render_app.py (5 new tests: accept_scene called/skipped/failure-notice, regenerate_snapshots_from called/failure-notice), and test/scene/cli/test_data.py (4 new continuity-snapshot get/delete tests, seeding via core.create_snapshot directly since there's deliberately no CLI create command).

test/scene/cli/** is fully green (107 passed), pdm run lint is clean, and `scene-data continuity-snapshot --help` shows get/delete. Full repo suite: 454 passed, 0 failed (up from 444 before this encounter). Next: e010-continuity-snapshot-gui, the final encounter in this campaign.
