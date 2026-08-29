---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-29T17:38:44Z'
depends_on: []
kind: scripted
name: c009-capture-model-reasoning
regions:
- agent
- cli
- core
- data
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-29T19:10:00Z'
---

# Capture model reasoning for rendering and continuity snapshots

## Requirements

1. Add two new **optional** (nullable) columns:
   - `rendering.body_reasoning` — the reasoning/thinking output the model produced
     while generating that rendering's `body`, if any.
   - `continuity_snapshot.narrative_state_reasoning` — the reasoning/thinking output
     the model produced while generating that snapshot's `narrative_state`, if any.
   Both must be optional because not every model used for these calls supports or
   returns a reasoning output.
2. Both the rendering agent (`scene.agent.rendering`) and the continuity agent
   (`scene.agent.continuity`) must work correctly against **both** reasoning and
   non-reasoning models, symmetrically:
   - litellm exposes reasoning as `reasoning_content` on both the streamed delta
     (rendering) and the non-streaming message (continuity) — but when a model
     doesn't return reasoning, litellm does not merely set that attribute to
     `None`, it deletes the attribute entirely. Every read of it must therefore
     use `getattr(obj, "reasoning_content", None)` (never direct attribute
     access, and never assume presence), on both agents.
   - When no reasoning is returned, the agents must produce a clean empty/`None`
     result (not raise, not fabricate placeholder text) — placeholder text for
     "this model doesn't support reasoning" is a GUI display-time concern (see
     requirement 4), not something the agents themselves should ever generate.
   - Whatever reasoning content *is* captured must be made available to callers
     alongside the final text, so every caller that persists a `Rendering` or
     `ContinuitySnapshot` can save it.
3. Every place that currently saves a `Rendering` or `ContinuitySnapshot` after a
   model call — the GUI's `RenderingColumn` (`src/scene/gui/rendering_column.py`)
   and the Textual TUI's `RenderApp` (`src/scene/cli/render_app.py`) for renderings,
   and `scene.agent.continuity.accept_scene` for snapshots — must pass the captured
   reasoning through (as `None` when the agent captured none), so the new columns
   are actually populated regardless of which front end produced the data, and
   regardless of whether the configured model supports reasoning.
4. The GUI's rendering screen must not change how generation is streamed — it still
   shows all model output (reasoning and prose) live in the Prose tab exactly as it
   does today. Once generation is complete and a version is saved or reselected, add
   two new **read-only** tabs to `RenderingColumn.tabs`:
   - "Prose Reasoning" — shows the selected rendering's `body_reasoning`.
   - "Continuity Snapshot Reasoning" — shows the current continuity snapshot's
     `narrative_state_reasoning`.
   If the relevant record exists but has no captured reasoning (the model didn't
   support it), the tab must say so explicitly rather than being blank — e.g. "The
   model used did not support a reasoning output." When there is no rendering or no
   continuity snapshot at all yet, reuse the existing "nothing yet" placeholder text
   for that tab instead of the no-reasoning message, so it isn't misread as "this
   model didn't support reasoning."
5. Update `docs/data-model-v2.md` directly to document both new columns (table rows
   and the `CREATE TABLE` SQL for `rendering` and `continuity_snapshot`), then add an
   `## Amendments` section at the bottom of the file describing this change as a
   dated amendment to the v2 model, rather than rewriting the document as if these
   fields had always been there.

## Rationale

Some of the models used for scene rendering and continuity-snapshot generation
produce a visible reasoning/thinking trace before their final answer; many others
(especially smaller self-hosted models this project targets — see
`docs/data-model-v2.md`'s note on `continuity_snapshot.narrative_state` being
designed for "smaller self-hosted models") do not. The trace that reasoning models
do produce currently streams through the GUI live (mixed into the same output the
user watches generate) but is then discarded — it isn't saved anywhere, so once
generation finishes there's no way to go back and read why the model made a given
choice. Persisting it (as optional columns, since only some models emit it) and
surfacing it in its own tab lets the user review that reasoning after the fact
without disturbing the existing live-streaming display or the prose-only tab it
already shows once a version is saved — and it must degrade cleanly to "no
reasoning captured" for every non-reasoning model this project also has to
support, never erroring or leaving stale reasoning from an earlier scene showing.

## Plan

1. **Data layer** — in `src/scene/data/rendering.py`, add
   `body_reasoning: Mapped[str | None] = mapped_column(String, nullable=True)` to
   `Rendering`. In `src/scene/data/continuity_snapshot.py`, add
   `narrative_state_reasoning: Mapped[str | None] = mapped_column(String, nullable=True)`
   to `ContinuitySnapshot`. No migration tooling exists in this project (schema is
   created via `Base.metadata.create_all`, and the `data/` database file is
   gitignored), so no migration script is needed.
2. **Core layer** — in `src/scene/core/rendering.py`, add an optional
   `body_reasoning: str | None = None` parameter to `create_rendering`, passed
   through to the `Rendering(...)` constructor. In
   `src/scene/core/continuity_snapshot.py`, add an optional
   `narrative_state_reasoning: str | None = None` parameter to `create_snapshot`,
   passed through similarly.
3. **Rendering agent** (`src/scene/agent/rendering.py`) — add a `reasoning: str = ""`
   field to the `RenderComplete` dataclass. In `stream_render`, accumulate reasoning
   chunks into a `reasoning_parts: list[str]` alongside the existing
   `content_parts` (the existing read already uses
   `getattr(delta, "reasoning_content", None)`, so no change needed there — just
   accumulate what it already yields), and yield
   `RenderComplete(text="".join(content_parts), reasoning="".join(reasoning_parts))`.
   For a stream with no reasoning deltas at all, `reasoning_parts` stays empty and
   `RenderComplete.reasoning == ""`.
4. **Continuity agent** (`src/scene/agent/continuity.py`) — add a frozen dataclass
   `ContinuityEditResult` with `narrative_state: str` and
   `narrative_state_reasoning: str = ""`. Change `run_continuity_edit` to read
   `response.choices[0].message.content` for the narrative state and
   `getattr(response.choices[0].message, "reasoning_content", None) or ""` for the
   reasoning (defensive `getattr`, matching the rendering agent, since litellm
   deletes the attribute rather than nulling it for non-reasoning models), and
   return a `ContinuityEditResult`. Update `accept_scene` to unpack that result and
   call
   `create_snapshot(session, story_id, scene_id, result.narrative_state, narrative_state_reasoning=result.narrative_state_reasoning or None)`
   — `or None` so an empty string (non-reasoning model) is stored as SQL `NULL`,
   not an empty string, matching the rendering path.
5. **CLI TUI** (`src/scene/cli/render_app.py`) — in `_RenderScreen._render_scene`,
   capture the final `RenderComplete` event's `.reasoning` (the loop currently only
   branches on `RenderContentDelta`/`RenderReasoningDelta`; add a branch that stores
   it) and pass `body_reasoning=<captured> or None` into the existing
   `create_rendering(...)` call.
6. **GUI** (`src/scene/gui/rendering_column.py`):
   - Add `PROSE_REASONING_TAB_LABEL = "Prose Reasoning"`,
     `CONTINUITY_SNAPSHOT_REASONING_TAB_LABEL = "Continuity Snapshot Reasoning"`, and
     `NO_REASONING_TEXT = "The model used did not support a reasoning output."`
     module-level constants.
   - Add `self.body_reasoning_view` and `self.continuity_snapshot_reasoning_view`
     (read-only `QPlainTextEdit`s), added to `self.tabs` in this order: Prose,
     Prose Reasoning, Continuity Snapshot, Continuity Snapshot Reasoning.
   - In `_refresh()`, populate `body_reasoning_view`: `NO_RENDERINGS_TEXT` when there
     are no renderings at all, otherwise `selected.body_reasoning or NO_REASONING_TEXT`.
   - In `_on_version_selected()`, populate `body_reasoning_view` from
     `rendering.body_reasoning or NO_REASONING_TEXT`.
   - In `_refresh_continuity_snapshot()`, populate `continuity_snapshot_reasoning_view`:
     empty when no scene/story is selected, `NO_CONTINUITY_SNAPSHOT_TEXT` when no
     snapshot exists, otherwise `snapshot.narrative_state_reasoning or NO_REASONING_TEXT`.
   - Track `self._reasoning_text`, reset alongside `self._content_text` in
     `_start_generation`. In `_on_render_event`, add a branch for `RenderComplete`
     that sets `self._reasoning_text = event.reasoning` (streaming display itself is
     unchanged — reasoning deltas still append into `_display_text` exactly as today).
   - In `_on_generation_finished()`, pass
     `body_reasoning=self._reasoning_text or None` into the existing
     `create_rendering(...)` call — so a non-reasoning model's generation (empty
     `_reasoning_text`) saves `NULL` and the Prose Reasoning tab falls back to
     `NO_REASONING_TEXT` on the very next refresh.
7. **Docs** — update `docs/data-model-v2.md`'s `Rendering` and `Continuity snapshot`
   sections (table + `CREATE TABLE` SQL) to include the two new nullable columns,
   then append a dated `## Amendments` section at the end of the file describing
   this addition and why the fields are optional.
8. **Tests** — update/add cases mirroring each changed module, with explicit
   coverage of both the reasoning-model and non-reasoning-model paths at every
   layer:
   - `test/scene/data/test_rendering.py`, `test/scene/data/test_continuity_snapshot.py`:
     construct a row with and without the new column.
   - `test/scene/core/test_rendering.py`, `test/scene/core/test_continuity_snapshot.py`:
     cover passing and omitting the new optional parameter.
   - `test/scene/agent/test_rendering.py`: update the existing `RenderComplete`
     equality assertions for the new field; add a case where reasoning deltas
     across multiple chunks are aggregated into the final `RenderComplete.reasoning`;
     and a case with only content deltas (no `reasoning_content` on any delta,
     mirroring a non-reasoning model) asserting `RenderComplete.reasoning == ""`.
   - `test/scene/agent/test_continuity.py`: update `run_continuity_edit`/`accept_scene`
     tests for the new `ContinuityEditResult` return type, with one fake message
     that sets `reasoning_content` and one that omits the attribute entirely
     (matching litellm's actual non-reasoning-model behavior, not just `None`),
     asserting the latter yields `narrative_state_reasoning == ""` and, through
     `accept_scene`, a snapshot with `narrative_state_reasoning is None`.
   - `test/scene/cli/test_render_app.py`: add a case asserting a scene rendered with
     reasoning deltas persists `body_reasoning` on the saved `Rendering`, and a case
     with no reasoning deltas asserting it is saved as `None`.
   - `test/scene/gui/test_rendering_column.py`: add cases for the two new tabs'
     presence/order/labels, the no-reasoning fallback text on a rendering/snapshot
     that has none, the "nothing yet" placeholder text taking precedence when there
     is no rendering/snapshot at all, a generation with reasoning deltas ending up
     in `body_reasoning_view` after it completes, and a generation with *no*
     reasoning deltas ending up showing `NO_REASONING_TEXT` after it completes.

## Verification

- `pdm run pytest` passes, including all new/updated cases listed above — in
  particular the non-reasoning-model paths in both agents' test suites.
- `pdm run lint` is clean.
- Launch `pdm run scene-writer`, render a scene with a reasoning-capable model
  configured, and confirm the Prose Reasoning and Continuity Snapshot Reasoning
  tabs show the captured reasoning, the live streaming view is unchanged (still
  shows all output, unsplit), and re-running against a non-reasoning model shows
  `NO_REASONING_TEXT` in both new tabs instead of stale or blank content.

## Log

### Review - 2026-08-29T18:10:48Z - John Hoff

Reviewed against the two applicable world lore items (linting, unit-testing); both are explicitly honored. The Plan enumerates a mirrored test file for every source module it touches (data, core, agent, cli, gui layers), with explicit reasoning/non-reasoning-model coverage at each layer per the unit-testing lore's path-mirroring convention, and Verification requires both pdm run pytest and pdm run lint to pass cleanly per the linting lore. No conflicts or gaps found within the cited surface; approved as reviewable.

### Message - 2026-08-29T18:24:47Z - John Hoff

Implementation deviation from Plan steps 5 and 6: rather than capturing reasoning only from the final RenderComplete event, both the CLI (RenderScreen._render_scene) and the GUI (RenderingColumn._on_render_event/_start_generation/_on_generation_finished) accumulate reasoning incrementally from each RenderReasoningDelta as it streams, mirroring how content_parts/_content_text already work. Reason: the cancellation path in both callers breaks out of the event loop as soon as is_cancelled is seen, before the generator ever yields its final RenderComplete event — relying solely on RenderComplete.reasoning would silently drop any reasoning that had already streamed in a cancelled generation, while assembled prose content would still be saved via content_parts. Incremental accumulation keeps reasoning consistent with the existing partial-save-on-cancel behavior. RenderComplete.reasoning (added per Plan step 3) is still populated correctly by stream_render and covered by its own agent-level tests, it's just not what either caller reads from. All layers implemented (data, core, both agents, CLI, GUI, docs) with full test coverage per Plan step 8; pdm run pytest (510 passed) and pdm run lint both clean.

### Completed - 2026-08-29T19:10:00Z - John Hoff

Verified: pdm run pytest (510 passed) and pdm run lint clean. User hit a local dev-database schema gap after implementation (existing data/scene.db predated the new columns, and this project's schema creation only creates missing tables, never alters existing ones) — fixed by ALTER TABLE ADD COLUMN against the user's local db, preserving existing rows; no code or migration tooling change was needed since data/ is gitignored and a fresh database always gets the new columns via create_all. User confirmed the underlying query error was resolved.
