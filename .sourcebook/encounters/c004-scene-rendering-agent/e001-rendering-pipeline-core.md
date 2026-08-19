---
archived: false
campaign: c004-scene-rendering-agent
created_by: John Hoff
created_on: '2026-08-19T00:52:02Z'
depends_on: []
kind: scripted
name: e001-rendering-pipeline-core
regions:
- agent
status: completed
updated_by: John Hoff
updated_on: '2026-08-19T03:21:59Z'
---

# E001 — Rendering Pipeline Core

## Requirements
- Add `scene/agent/rendering.py` (a flat module, consistent with `scene.agent.llm`/`config`/`registry`/`role`, not a package — there's no tool registry or multi-file concern here to justify one) with:
  - `find_next_unrendered_scene(session, story_id) -> Scene | None` — returns the lowest-position scene in the story with no active rendering (checked via `scene.core.rendering.list_renderings` and each `Rendering.is_active`), or `None` if every scene already has an active rendering (including the zero-scenes case).
  - `build_render_messages(session, story_id, target_scene_id) -> list[dict[str, Any]]` — builds a fresh LiteLLM-style messages list from scratch: a system message combining the story's `scenario` and `style_guidance`; then, for every scene strictly before the target scene's position (ordered by position), a user message with that scene's full detail (heading, description, required_actions, length) plus its assigned characters (`scene.core.scene_character.list_characters_for_scene`, each with name/description/motive) and locations (`scene.core.scene_location.list_locations_for_scene`, each with name/description), followed by an assistant message equal to that scene's active rendering body — raising `ValueError` if a prior scene has no active rendering (should never happen when reached via `find_next_unrendered_scene`, but must fail loudly rather than silently produce a context gap); and a final user message with the target scene's own full detail (same shape as above) plus an instruction to write that scene's prose now.
  - Streaming event dataclasses `RenderReasoningDelta`, `RenderContentDelta`, and `RenderComplete` (frozen, `RenderComplete` carrying the fully assembled text), and a generator `stream_render(config, messages) -> Iterator[RenderReasoningDelta | RenderContentDelta | RenderComplete]` that consumes `scene.agent.llm.stream_complete(config, messages)` (no `tools` argument) the same way `scene.agent.coordinator.loop.run_turn` consumes its stream — accumulating reasoning/content deltas and yielding a final `RenderComplete` once the stream ends. No tool-call handling of any kind: this pipeline never calls tools.
- Cover `find_next_unrendered_scene` and `build_render_messages` with unit tests against a real (test) database, seeding story/scenes/characters/locations/renderings (mirroring `test_scene.py`'s fixture style), including: no scenes; all scenes already rendered; correct character/location detail inclusion in a prior scene's message; and the `ValueError` for a prior scene with no active rendering. Cover `stream_render` with a scripted `stream_complete` mock (mirroring `test_loop.py`'s `FakeChunk`/`make_chunk`/`make_scripted_stream_complete` pattern), verifying reasoning/content deltas stream correctly and `RenderComplete`'s assembled text matches the concatenated content.

## Rationale
This is the campaign's foundational encounter — the pure, non-interactive rendering pipeline
(context reconstruction plus streaming generation) with zero TUI involvement, so it can be
fully unit-tested against a real test database and a scripted LLM stream before any
interactive surface is built on top of it in `e002`. Establishes the reconstructed-context
design from the campaign body: every call rebuilds its message list from the database's
currently-active renderings, so switching which rendering is active for an earlier scene
transparently changes the continuity context for every later regeneration, with no separate
invalidation step needed.

## Plan
1. Add `scene/agent/rendering.py` with `find_next_unrendered_scene`, `build_render_messages`, the `RenderReasoningDelta`/`RenderContentDelta`/`RenderComplete` event dataclasses, and `stream_render`, per Requirements.
2. Add tests under `test/scene/agent/test_rendering.py` covering `find_next_unrendered_scene` and `build_render_messages` against a seeded test database, and `stream_render` against a scripted `stream_complete` mock.
3. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green.
- `pdm run lint` reports zero errors.
- No manual/TUI verification for this encounter — there's no interactive surface yet; that begins in `e002-render-tui`.

## Log

### Review - 2026-08-19T03:09:15Z - John Hoff

Reviewed e001-rendering-pipeline-core against the linting and unit-testing lore and against c004's design decisions: both lore items are explicitly honored (Plan/Verification require pdm run lint and pdm run pytest clean, with tests correctly mirrored under test/scene/agent/test_rendering.py), and the Plan's technical claims — reconstructed-context message shape, plain-completion streaming mirroring run_turn, flat sibling module placement, and every referenced scene.core/scene.agent API — check out against the actual code they cite, with no fabricated APIs or scope creep into the coordinator's tool-calling loop. One point is noted but not a defect: stream_render takes a pre-built config rather than calling get_llm_config(AgentRole.RENDERING) itself, leaving that wiring for the not-yet-specified e002 TUI encounter, which is a reasonable split but unverifiable from this encounter alone. PASS-WITH-NOTES.

### Completed - 2026-08-19T03:21:59Z - John Hoff

Verified: pdm run pytest passes 277/277 with 100% coverage, pdm run lint zero errors. Delivered scene/agent/rendering.py: find_next_unrendered_scene (lowest-position scene without an active rendering, or None), build_render_messages (system message from story scenario/style_guidance, one user/assistant pair per prior scene using its full detail plus assigned characters/locations and its active rendering body, final user message for the target scene; raises ValueError for a missing story/scene or a prior scene with no active rendering), and the RenderReasoningDelta/RenderContentDelta/RenderComplete event dataclasses plus stream_render, a generator consuming scene.agent.llm.stream_complete with no tools argument. Covered by test/scene/agent/test_rendering.py: find_next_unrendered_scene (no scenes, all rendered, lowest-unrendered), build_render_messages (system content, no-prior-scenes shape, prior-scene detail/active-rendering inclusion, character/location detail, the context-gap ValueError, missing story/scene errors), and stream_render against a scripted stream_complete mock (content deltas, reasoning deltas, empty-stream case). No manual/TUI verification for this encounter per its Verification section — the interactive surface begins in e002-render-tui.
