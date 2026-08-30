---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-30T19:04:26Z'
depends_on: []
kind: scripted
name: e016-continuity-summarization
regions:
- agent
status: completed
updated_by: John Hoff
updated_on: '2026-08-30T19:30:38Z'
---

## Requirements

Rewrite the continuity-editing agent's system prompt
(`agent-prompts.yaml`'s `continuity_editor.system_prompt`, loaded via
`load_prompts().continuity_editor_system_prompt` in
`src/scene/agent/continuity.py`) so the canonical narrative state it produces
behaves as a **summary of the story's current state**, not an **append-only
log of events**:

- The model must fold each newly accepted scene's consequences into the
  existing narrative state — updating, merging, or replacing what the scene
  changes — rather than appending the scene as one more entry onto a
  growing list.
- Once a detail no longer matters for future scenes (a resolved thread, a
  passing detail, a superseded fact), the model should drop it instead of
  carrying it forward indefinitely.
- The state should stay organized by what it describes (characters,
  locations, ongoing plot threads) rather than as a chronological record of
  what was learned in which scene.
- The state's length should track what currently matters to the story, not
  the number of scenes that have occurred — it should not grow roughly
  linearly as the story goes on.
- The existing safeguards against fabrication stay in place unchanged: only
  add facts directly stated or unambiguously shown in the scene; never infer
  unstated motives, identities, timelines, or future events; never resolve
  an open thread unless the scene explicitly resolves it; return the state
  only, with no analysis, explanations, or scene prose.

No changes to `src/scene/agent/continuity.py`, `scene.core`, or the
`ContinuitySnapshot` data model — this is a prompt-content change only. The
mechanics of building continuity messages, calling the LLM, and persisting
the result are already wording-agnostic.

## Rationale

The user reported that continuity snapshots read fine for the first 2-3
scenes but become unwieldy by 6+ scenes. Reading the current prompt
confirms why: its rules are unconditionally additive — "Preserve all prior
facts unless the new scene explicitly changes them" and "Add only facts
directly stated or unambiguously shown in the scene" — with nothing telling
the model to consolidate, reorganize, or drop material that's no longer
load-bearing. Combined with "using the supplied snapshot format" (an
implicit format inherited from whatever the prior state already looked
like, never an explicit structure), the natural drift under those rules is
exactly what the user described: each scene's edit mostly just appends onto
what came before, so the state grows roughly linearly with scene count
instead of staying a right-sized picture of where the story currently
stands. `build_render_messages` (`src/scene/agent/rendering.py`) then feeds
this growing state into every subsequent scene's `## Current Canon`
section verbatim, so the problem compounds: later scenes get an
increasingly bloated context.

The fix is entirely in the prompt's instructions, not the surrounding code
— `build_continuity_messages`/`accept_scene`/`stream_accept_scene`/
`regenerate_snapshots_from` (`src/scene/agent/continuity.py`) just fetch the
preceding snapshot, hand it to the model with the newly accepted scene, and
persist whatever text comes back; none of that logic assumes anything about
the state's internal shape or growth pattern. This mirrors
`e002-rendering-prompt-structure`'s precedent of treating a prompt-quality
problem as a content change to `agent-prompts.yaml` rather than a code
change, verified the same way that encounter was: full test-suite pass plus
manual inspection (there, of `build_render_messages`' rendered messages;
here, of the actual narrative-state text a real multi-scene story produces),
since no automated test can meaningfully assert that LLM-authored prose
"reads as a summary" versus "reads as a log."

The rewritten rules keep every existing anti-fabrication safeguard
unchanged (only stated/unambiguous facts, no inferred motives/timelines/
future events, no unrequested thread resolution, state-only output) —
this encounter narrows scope to the growth/log-vs-summary problem alone,
not a broader rewrite of what the continuity editor is allowed to do.

## Plan

1. In `agent-prompts.yaml`, replace `continuity_editor.system_prompt` with:

   ```yaml
   continuity_editor:
     system_prompt: |-
       You are the continuity editor for a serialized novel.

       You maintain a single canonical narrative state: a compact snapshot of
       where the story stands right now, not a log of everything that has
       happened. Given the current narrative state and one newly accepted
       scene, write the updated narrative state.

       Rules:
       - Fold the scene's consequences into the existing state; do not simply
         append it as a new entry. Update or replace details the scene
         changes, and merge related facts together instead of restating them
         separately.
       - Once a detail no longer matters for future scenes — a resolved
         thread, a passing detail, a superseded state — drop it rather than
         carrying it forward. You are maintaining relevance, not an archive.
       - Preserve facts the scene doesn't touch only insofar as they still
         matter going forward.
       - Add only facts directly stated or unambiguously shown in the scene.
       - Do not infer unstated motives, identities, timelines, or future events.
       - Do not resolve an open thread unless the scene explicitly resolves it.
       - Group related facts together (by character, location, or plot thread)
         rather than listing them in the order they were learned, so the state
         stays easy to scan no matter how many scenes have occurred.
       - The state's length should track what currently matters to the story,
         not the number of scenes so far — if it is growing steadily longer as
         scenes accumulate, that means older detail needs compressing or
         cutting, not that it should keep expanding.
       - Return the updated narrative state only. Do not include analysis,
         explanations, or the scene prose.
   ```

   Keep the surrounding file's header comment for the `continuity_editor` section
   accurate to this new framing (it already describes the section correctly at a
   high level — only touch it if the rewrite makes any word there inaccurate).

2. No other files change. `PromptSet.continuity_editor_system_prompt` and every
   call site that consumes it (`src/scene/agent/continuity.py`,
   `src/scene/agent/rendering.py`'s consumption of the resulting snapshot) are
   unaffected by wording alone.

## Verification

- `pdm run pytest` — full suite passes unchanged (no code or test changes are
  expected; this confirms the prompt-content edit didn't break YAML parsing or
  `load_prompts()`).
- `pdm run lint` — clean (ruff, 120-char line length; N/A to the YAML edit
  itself, but confirms nothing else was inadvertently touched).
- Manual smoke check via the `run` skill: using a story with 6+ rendered
  scenes (regenerating continuity snapshots forward from scene 1 with
  `regenerate_snapshots_from`/the GUI's Render Full Story flow, or the
  `scene-coordinator`/GUI continuity acceptance flow scene by scene),
  inspect the narrative state at scenes 1, 3, and 6+ and confirm: the state
  reads as an organized summary of current story state rather than a
  chronological list of past events; its length does not grow roughly
  linearly with scene count; established facts still carry forward
  correctly (no regressions in continuity accuracy) even as older,
  no-longer-relevant detail drops out.

## Log

### Review - 2026-08-30T19:08:32Z - John Hoff

Reviewed against the two applicable lore items (linting, unit-testing): both are honored — the change is pure YAML prompt content with no Python touched, so linting is a no-op confirmed rather than skipped, and the unit-testing requirement is satisfied via a full pdm run pytest pass plus a manual multi-scene smoke check, consistent with the cited e002 precedent that prose-quality changes can't be asserted by automated tests. The reviewer verified the encounter's factual claims directly: the quoted current continuity_editor.system_prompt text matches agent-prompts.yaml verbatim, and src/scene/agent/continuity.py/rendering.py treat the narrative state as an opaque string with no format assumptions, confirming both files are genuinely unaffected by wording alone. The reviewer flagged one unverified concern — whether test/scene/agent/test_prompts.py hard-codes the real prompt text — which is resolved: that test file uses fully synthetic placeholder prompt content (e.g. "Continuity prompt.") written to a tmp_path fixture file, never the real agent-prompts.yaml wording, so this change cannot break it. PASS-WITH-NOTES.

### Completed - 2026-08-30T19:30:38Z - John Hoff

Verification passed: pdm run pytest (616 tests, unchanged) and pdm run lint both clean. Manual smoke test using the real configured continuity-editing model (openrouter-instruct) across a synthetic 6-scene story confirmed the intended behavior change: the narrative state grew normally while threads were open (211/302/354/550 chars across scenes 1-4) but shrank once the debt/satchel subplot resolved (406 chars at scene 5, 314 at scene 6), with the model explicitly noting the resolved thread was "no longer relevant" -- the state is now organized by what currently matters rather than growing as an append-only log.
