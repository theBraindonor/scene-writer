---
archived: false
campaign: c008-story-data-model-v2
created_by: John Hoff
created_on: '2026-08-24T19:50:16Z'
depends_on: []
kind: unscripted
name: e011-render-model-token-budget-fix
regions:
- agent
- cli
status: completed
updated_by: John Hoff
updated_on: '2026-08-24T20:16:37Z'
---

# Render TUI fixes found during manual verification

## Requirements

While the user manually verified `e009-continuity-snapshot-cli`'s render TUI
against real models, three separate problems surfaced. All three are
recorded here together since they were found and fixed in the same
verification pass; none of them are defects introduced by this campaign's
`e001`-`e010` plans, and none of them were (or could have been) caught by
the existing mocked/stubbed test suite, since none of it exercises a real
LLM or a real running Textual app.

### 1. Reasoning models could silently drop the whole scene

Using `SCENE_RENDERING_AGENT=openrouter-roleplay`
(`openrouter/aion-labs/aion-3.0-mini`, a reasoning-capable model), scene
rendering produced no prose at all: the output pane only ever showed
"thinking" text, and nothing was persisted to the database for that scene.

Root cause: `scene.agent.llm._build_kwargs` never set `max_tokens` (or any
other completion-length control) on the outbound `litellm.completion(...)`
call, and `scene.agent.registry.ModelProfile` had no field to configure one
per profile. A reasoning model with no `max_tokens` override can exhaust its
entire default completion budget emitting `reasoning_content` ("thinking")
before ever reaching the point of emitting `content` (the actual scene); the
stream then ends with no content deltas, so `RenderScreen._render_scene`'s
`assembled` string stays empty and `if assembled:` never fires.

Fixed by:

- `src/scene/agent/registry.py`: `ModelProfile` gained two new optional
  fields, `max_tokens: int | None = None` and `reasoning_effort: str | None
  = None`, parsed from the corresponding optional YAML keys in
  `load_registry`.
- `src/scene/agent/config.py`: `LLMConfig` gained the same two optional
  fields; `get_llm_config` threads `profile.max_tokens`/
  `profile.reasoning_effort` through into the returned `LLMConfig`.
- `src/scene/agent/llm.py`: `_build_kwargs` now includes `max_tokens`/
  `reasoning_effort` in the outbound kwargs whenever the resolved
  `LLMConfig` sets them (both remain omitted, i.e. no behavior change, for
  any profile that doesn't set them).
- `models.example.yaml`: documented both new optional fields and added an
  example reasoning-model profile (`openrouter-reasoning-roleplay`) showing
  `max_tokens` set.
- The user's local (gitignored) `models.yaml`: added `max_tokens: 4096` to
  the `openrouter-roleplay` profile actually in use.

Verified directly against the real API (not just mocked tests): calling
`scene.agent.llm.complete` with the fixed `openrouter-roleplay` profile
against a real rendering-style prompt now returns `finish_reason: "stop"`
with the actual scene prose in `.content` and the model's reasoning
correctly separated into `.reasoning_content`.

### 2. Streaming output visibly "bounced" as text arrived

Once (1) was fixed and prose actually started streaming, the user reported
the live output display was "bouncing all over" as content arrived, hard to
read or even fully characterize.

Root cause: `RenderScreen._start_output`/`_append_output` streamed into a
Textual `Markdown` widget, calling `.update(self._output_text)` — a full
Markdown re-parse of the *entire* accumulated text — on every single
streamed delta. Partial markdown tokens (a lone `*`, a line-leading `1.`,
etc.) get reinterpreted differently as more text arrives, so the rendered
layout visibly reflows/jumps mid-stream. Scene prose isn't structured
Markdown in the first place, and the app already displays a saved
rendering's body as plain text elsewhere (`#version-text` is a `Static`, not
a `Markdown`) — the live pane was the only place still doing this.

Fixed by switching `#output-text` from a `Markdown` widget to a `Static`
widget in `src/scene/cli/render_app.py`, so streamed text is displayed
verbatim with no re-parsing. Updated `test/scene/cli/test_render_app.py`'s
`Markdown`/`.source` references to `Static`/`.content` to match.

### 3. No visibility into the resulting continuity snapshot

The user asked to see the continuity snapshot for the currently selected
scene displayed below the scene rendering in the render TUI (this campaign's
`e010-continuity-snapshot-gui` plans an equivalent panel for the Qt GUI, but
that's separate, later work — this is specifically about `render_app.py`,
which is what the user has been testing against).

Added a "Continuity Snapshot" section (a label + a new `#continuity-snapshot-text`
`Static`) to `RenderScreen`, positioned directly below the output pane and
above the Versions section. `_refresh_continuity_snapshot` looks up
`core.continuity_snapshot.get_snapshot(session, story_id, selected_scene_id)`
for the currently selected scene and shows its `narrative_state`, or a
"(No continuity snapshot yet.)" placeholder. It's called from
`_refresh_scenes` (covering `on_mount`, the end of `_render_scene`,
`_activate_selected_version`, and `_delete_selected_version`, all of which
already called `_refresh_scenes`), from `on_list_view_highlighted`'s
scene-selection branch (which updates scene detail directly without going
through `_refresh_scenes`), and from `_regenerate_snapshots`'s `finally`
block (so the panel reflects the outcome whether regeneration succeeds or
fails).

## Rationale

All three were found by the user exercising the actual render TUI against
real models and real interaction, which is exactly the kind of gap a mocked
test suite can't close — `stream_render`/`accept_scene`/
`regenerate_snapshots_from` are stubbed in every existing test, so neither
the token-budget exhaustion, the Markdown reflow, nor the desire to see the
resulting continuity snapshot could have been caught without a human
actually running the app. Recorded here as one unscripted encounter (per the
user's request) since all three were found and fixed in the same
verification pass on this campaign's generation-path work, even though (1)
and (2) are pre-existing gaps predating `c008` and (3) is new scope the user
asked for directly, rather than something `e009`/`e010` already planned for
the CLI.

Fix (3) intentionally does not touch `src/scene/gui/rendering_column.py` —
`e010-continuity-snapshot-gui`'s own plan already covers an equivalent panel
for the Qt GUI as separate, later work; the user confirmed this fix is CLI
(`render_app.py`) only for now.

## Testing

- `test/scene/agent/test_registry.py`, `test_config.py`, `test_llm.py`:
  new/updated cases for `max_tokens`/`reasoning_effort` profile parsing,
  threading through `LLMConfig`, and inclusion in outbound completion
  kwargs.
- `test/scene/cli/test_render_app.py`: updated every `Markdown`/`.source`
  reference for `#output-text` to `Static`/`.content`; added four new tests
  for the continuity snapshot panel (placeholder when none exists, showing
  a pre-existing snapshot, updating after a generation is accepted, and
  updating after activating a different version).
- `pdm run pytest` passes (460 passed across the full repo, up from 454
  before this encounter) and `pdm run lint` reports no findings.
- Fix (1) was additionally verified directly against the real
  `openrouter-roleplay` API (not just mocked), confirmed by the user
  actually rendering a scene successfully afterward.

## Log

### Review - 2026-08-24T20:12:58Z - John Hoff

Reviewed against the linting and unit-testing lore (the only lore applicable to the agent/cli regions this encounter touches). All three recorded fixes were verified directly against the current code: ModelProfile/LLMConfig/_build_kwargs in src/scene/agent/{registry,config,llm}.py correctly add optional max_tokens/reasoning_effort pass-through with no behavior change when unset; render_app.py's #output-text is confirmed a Static (not Markdown) with the reflow rationale documented inline; and the #continuity-snapshot-text panel plus _refresh_continuity_snapshot are wired exactly where the encounter claims (_refresh_scenes, on_list_view_highlighted, _regenerate_snapshots's finally). Test coverage claims for all three fixes were confirmed present in test/scene/agent/test_{registry,config,llm}.py and test/scene/cli/test_render_app.py (including all four new continuity-snapshot tests), and re-running pdm run lint and pdm run pytest independently reproduced the claimed clean lint and 460-passed results. No lore conflicts and no unverifiable concerns found; approved as reviewed.

### Completed - 2026-08-24T20:16:37Z - John Hoff

Review raised nothing actionable -- no follow-up work needed. The user confirmed all three fixes are working correctly via their own manual testing against real models before this encounter was drafted for review, and the reviewer independently re-verified the code state, test coverage, and full-suite results. Closing out.
