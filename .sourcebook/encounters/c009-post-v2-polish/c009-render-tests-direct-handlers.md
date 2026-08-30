---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-30T01:13:10Z'
depends_on: []
kind: scripted
name: c009-render-tests-direct-handlers
regions:
- cli
status: completed
updated_by: John Hoff
updated_on: '2026-08-30T01:43:08Z'
---

## Requirements

Convert the interaction steps in `test/scene/cli/test_coordinator_app.py` and
`test/scene/cli/test_render_app.py` that currently drive `CoordinatorApp` /
`RenderApp` through Textual's simulated-input pipeline
(`pilot.click(...)`, `pilot.press(...)`, `pilot.pause()`) into direct calls on
the message handlers our own code defines (`on_button_pressed`,
`on_list_view_highlighted`, `on_list_view_selected`), combined with
deterministic completion signals we already own (`app.workers.wait_for_complete()`,
awaiting the `AwaitMount` returned by `app.push_screen(...)`), wherever doing
so doesn't remove real coverage. Exactly one click-driven "wiring" test per
screen, and the tests that specifically exercise real key-binding dispatch or
computed layout/geometry, are kept as genuine pilot-driven tests. All 50
existing tests in the two files must keep passing, with no reduction in what
each test actually verifies (same assertions on state/widget content).

## Rationale

Both files were flagged as suspiciously slow (34s of the full suite's 68s
total test time lives in these 50 of 523 tests) and initially suspected of
hiding unmocked database/LLM calls. Investigation ruled that out — the
`core` layer's 79 real-SQLite tests run in 1.23s total, and both files
already monkeypatch `stream_complete` everywhere it's called. Profiling
(`cProfile` over `test_coordinator_app.py`) instead found the cost
concentrated in `_overlapped.GetQueuedCompletionStatus` (11.5s cumulative)
and Textual's `_win_sleep.wait_inner` (1.4s self time) — Windows-specific
overhead from `textual/_win_sleep.py`, which pipes its internal
repaint/idle-detection sleep through a threadpool executor and a Windows
waitable timer for precision. `pilot.click()` calls this idle-detection
(`wait_for_idle()`) up to 4 times internally per call (once per synthesized
MouseDown/MouseUp/Click event, plus once more at the end) — Textual's own
implementation, not something test code added.

The deeper issue, not just the Windows timer cost: `pilot.click()` +
`pilot.pause()` makes these tests wait on an external library (Textual) to
notice and react to a synthesized input event via a CPU-idle heuristic,
rather than on a specific, owned completion signal — the hallmark of an
integration test, not a unit test, regardless of how fast it runs. A
same-assertions rewrite of `test_render_next_scene_streams_and_persists_active_rendering`
confirmed this empirically: calling `RenderScreen.on_button_pressed(...)`
directly and awaiting `app.workers.wait_for_complete()` (`call_from_thread`
blocks the calling thread until its callback has actually run, so
`wait_for_complete()` already guarantees every UI update from that worker is
applied — no `pilot.pause()` needed after it) cut the test from 1.40s to
0.94s measured via pytest's own `--durations`, while asserting the exact
same things. `app.push_screen(screen)` similarly returns an `AwaitMount` that
resolves once the screen (including its `on_mount()`) has fully mounted —
a deterministic replacement for `pilot.click(f"#story-{story_id}")` +
`pilot.pause()` used purely for navigation/setup.

What must stay pilot-driven, and why:
- `test_story_picker_lists_stories_and_selecting_shows_scenes` — the one
  test that should keep a real `pilot.click()` on a `StoryListItem`, as a
  smoke test that Textual is actually still delivering `ListView.Selected`
  the way `on_list_view_selected` expects (ID/selector drift, wiring).
- `test_ctrl_j_inserts_newline_instead_of_submitting` and
  `test_typing_a_printable_character_inserts_it` — these test our
  `ChatInput._on_key` override's interaction with Textual's real key
  dispatch; there's no meaningful "direct call" equivalent that still tests
  what these test.
- `test_escape_then_y_cancels_generation_and_saves_partial_content` and
  `test_escape_then_n_keeps_generation_running_to_completion` — these
  specifically verify the `BINDINGS` table (`escape`/`y`/`n` →
  `action_cancel_generation`/`action_confirm_cancel`/`action_dismiss_cancel`)
  is correctly wired through Textual's real key-binding dispatch; a direct
  `action_*()` call would silently pass even if a binding typo broke the
  keymap. They already use `gated_stream`/`wait_until` (deterministic
  polling on real state) rather than blind pauses, so only their setup
  navigation (`pilot.click(f"#story-{story_id}")`) should switch to
  `push_screen`, not the escape/y/n interaction itself.
- `test_message_blocks_stay_content_sized_and_transcript_scrolls`,
  `test_chat_input_shows_at_least_two_content_rows`,
  `test_transcript_auto_scrolls_on_every_streamed_event`,
  `test_ordered_list_does_not_blow_out_block_height` — these assert on
  Textual's actual computed layout (`styles.height`, `virtual_size`,
  `region.height`), which only exists once real rendering has happened;
  there's no non-pilot equivalent.
- `test_on_button_pressed_ignores_unrelated_buttons`,
  `test_on_list_view_highlighted_ignores_non_scene_items`,
  `test_action_cancel_generation_noop_without_active_worker`,
  `test_action_confirm_and_dismiss_cancel_noop_when_not_confirming`,
  `test_render_story_pane_handles_missing_story` — already direct-call,
  unchanged.

## Plan

1. In `test/scene/cli/test_render_app.py`, add small fake-event helpers next
   to the existing `FakeButton`-style pattern already used in
   `test_on_button_pressed_ignores_unrelated_buttons`
   (`FakeButtonPressed(button_id)`, `FakeListViewHighlighted(item)`) for
   constructing `Button.Pressed`/`ListView.Highlighted`-shaped fakes without
   mounting a real `Button`/`ListView`.
2. Replace every `pilot.click(f"#story-{story_id}")` setup line used purely
   for navigation with `await app.push_screen(RenderScreen(story_id))`,
   dropping the `pilot.pause()` that followed it — except in
   `test_story_picker_lists_stories_and_selecting_shows_scenes`, which keeps
   the real click.
3. Replace `pilot.click("#render-next")` / `"#regenerate"` /
   `"#activate-version"` / `"#delete-version"` with direct
   `screen.on_button_pressed(FakeButtonPressed("..."))` calls, keeping
   `await app.workers.wait_for_complete()` where the handler kicks off a
   `@work` — this covers
   `test_render_next_scene_streams_and_persists_active_rendering`,
   `test_render_next_scene_persists_reasoning_when_present`,
   `test_output_pane_auto_scrolls_on_every_streamed_chunk`,
   `test_render_next_scene_shows_notice_when_all_scenes_rendered`,
   `test_regenerate_creates_new_version_and_keeps_previous`,
   `test_activating_version_updates_active_indicator_and_scene_status`,
   `test_render_next_scene_calls_accept_scene_when_continuity_config_set`,
   `test_render_next_scene_skips_accept_scene_without_continuity_config`,
   `test_render_next_scene_shows_notice_when_accept_scene_fails`,
   `test_activating_version_calls_regenerate_snapshots_from_when_continuity_config_set`,
   `test_activating_version_shows_notice_when_regenerate_fails`,
   `test_continuity_snapshot_panel_updates_after_generation`,
   `test_continuity_snapshot_panel_updates_after_activating_version`,
   `test_delete_refuses_scene_sole_rendering`,
   `test_delete_refuses_currently_active_rendering`,
   `test_delete_removes_inactive_version`.
4. Replace `pilot.click("#scene-list")` + `pilot.press("down")` in
   `test_scene_list_highlight_updates_detail_pane`, and the
   `pilot.click(f"#version-{id}")` selection steps in the tests from step 3
   that select a version first, with direct
   `screen.on_list_view_highlighted(FakeListViewHighlighted(item))` calls,
   fetching the real `SceneListItem`/`VersionListItem` off the mounted
   `ListView` (e.g. `screen.query_one("#version-list", ListView).children[i]`)
   rather than fabricating one, since the handler reads `item.scene_id` /
   `item.rendering_id`.
5. Drop the now-setup-only `pilot.click`/`pilot.pause` pairs in
   `test_render_screen_shows_no_scenes_placeholder_when_story_has_no_scenes`,
   `test_continuity_snapshot_panel_shows_placeholder_when_none_exists`,
   `test_continuity_snapshot_panel_shows_saved_snapshot` in favor of
   `push_screen`.
6. In `test/scene/cli/test_coordinator_app.py`, remove the trailing
   `await pilot.pause()` in the shared `send()` helper — `wait_for_complete()`
   already guarantees every `call_from_thread`-issued update has applied, so
   it's dead weight for every test that goes through `send()`. Convert
   `test_thinking_toggle_expands_and_stays_expanded`'s
   `pilot.click("#thinking-toggle")` to a direct
   `block.on_button_pressed(FakeButtonPressed("thinking-toggle"))` call using
   the same fake-event helper pattern (mirrored locally in this file, or
   imported from a shared test helper module if one doesn't already exist).
7. Run the full `pdm run pytest test/scene/cli/test_coordinator_app.py
   test/scene/cli/test_render_app.py --no-cov --durations=0` before and after
   to confirm no regression in what's asserted and to record the wall-time
   delta in the completion message.
8. Run `pdm run lint` and the full `pdm run pytest` suite (with coverage, as
   normal) to confirm nothing else broke.

## Verification

- `pdm run pytest test/scene/cli/test_coordinator_app.py
  test/scene/cli/test_render_app.py -v` — all 50 tests still pass, same
  assertions as before (diff review confirms no assertion was weakened or
  removed, only how the interaction is driven).
- `pdm run pytest` (full suite, default coverage/HTML report) — all 523+
  tests pass.
- `pdm run lint` — clean.
- Wall-clock time for the two files (`--durations=0`, `--no-cov`) recorded
  before and after in the completion message to confirm a measurable
  reduction consistent with the ~33% per-test drop observed in the
  prototype rewrite.

## Log

### Review - 2026-08-30T01:15:16Z - John Hoff

Reviewed against the world-assigned `linting` and `unit-testing` lore (the only applicable lore; the `cli` region carries no region-specific lore of its own). The Plan explicitly runs `pdm run lint` and the full `pdm run pytest` suite with its default coverage/HTML report as completion gates, and requires all 50 existing tests in the two target files to keep passing with unchanged assertions — fully consistent with both lore items. The one `--no-cov` invocation in the Plan is clearly scoped to a supplementary wall-clock comparison, not a substitute for the lore-mandated default-coverage run performed separately. A spot-check of the named test files confirmed the cited test names, helper patterns, and `wait_for_complete()` usage are real, not fabricated. No conflicts found; PASS-WITH-NOTES.

### Completed - 2026-08-30T01:43:08Z - John Hoff

Converted test_render_app.py and test_coordinator_app.py to direct handler invocation + deterministic waits, keeping one real click-through test and the two real keybinding tests. All 50 tests pass; combined wall time 43.74s -> 38.20s (--no-cov), test_render_app.py alone 32.12s -> 14.67s. Full suite (523 tests) passes and lint is clean. Found and fixed two latent bugs surfaced by the conversion: a missing stop() no-op needed on the fake Button.Pressed event, and _activate_selected_version()'s chained _regenerate_snapshots() worker needing a second wait_for_complete() call since it's only registered after the first call's snapshot.
