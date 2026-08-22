---
archived: false
campaign: c007-rendering-prompt-quality
created_by: John Hoff
created_on: '2026-08-22T04:50:53Z'
depends_on: []
kind: unscripted
name: e001-fictional-framing-prefix
regions:
- agent
status: completed
updated_by: John Hoff
updated_on: '2026-08-22T15:29:42Z'
---

# E001 — Rendering Prompt Markdown Restructuring

## Requirements

Changes to `build_render_messages`' message construction in `src/scene/agent/rendering.py`:

1. Added a fiction-framing prefix, before the existing `Scenario:` line:

   > "You are a fiction writer drafting a scene of an ongoing story. This is a work of
   > fiction: the scenario and this scene's details have already been laid out ahead of
   > time by the story's author, so treat them as established facts of the story world
   > rather than something to invent, question, or reconsider. Your job is only to write
   > the requested scene's prose."

2. Removed the `"\n\nWrite this scene's prose now."` suffix that was appended to the target
   scene's final user message.

3. Extracted the closing system-message instruction into a named `fiction_suffix` variable,
   alongside the new `fiction_prefix`, and replaced its text with:

   > "The story's author will give you one scene at a time, in the order that they will
   > appear in the larger story. You will need to complete the scene so that the next scene
   > of the story can be written. It is important that you include all required elements—they
   > are intended to provide the spine of continuity for the story."

4. Gave `Scenario`/`Style Guidance` the same markdown heading treatment as the rest of the
   system prompt: `f"## Scenario\n\n{story.scenario}"` and `f"## Style Guidance\n\n{...}"`.

5. Moved full character and location details out of each per-scene message and into two new
   markdown system-prompt sections, `_character_roster_markdown` (`## Characters`) and
   `_location_roster_markdown` (`## Locations`), each a bullet list (`- **Name**: description
   (Motive: motive)` / `- **Name**: description`) sourced from the full story-wide roster
   (`scene.core.character.list_characters` / `scene.core.location.list_locations`), inserted
   between `## Style Guidance` and `fiction_suffix`.

6. Restructured `_scene_detail_text` (the per-scene user message, used for every prior scene and
   the target scene) into markdown sections: a `# Scene: {heading}` title (scene position number
   deliberately excluded from the title), then `## Length`, `## Description`, `## Locations`
   (comma-delimited names only), `## Characters` (comma-delimited names only), and
   `## Required Elements` last — renamed from `## Required Actions` (the underlying
   `scene.required_actions` data attribute and every other "Required Actions" label elsewhere in
   the app, e.g. the GUI entity column's form field, are deliberately left unrenamed for now,
   per explicit direction). Blocks are joined with blank lines (`"\n\n".join(...)`) instead of
   the previous single-newline `Label: value` lines.

No change to message assembly order otherwise, or any other part of the rendering pipeline
(streaming, persistence, GUI/CLI/TUI surfaces) — the Textual TUI's own `_scene_detail_text` in
`src/scene/cli/render_app.py` (a separate, identically-named function for its own on-screen
scene-detail pane, not for prompt construction) is untouched.

`test/scene/agent/test_rendering.py` updated throughout: removed the stale
`"Write this scene's prose now."` assertion; replaced the old character/location-detail test
with `test_build_render_messages_scene_message_lists_character_and_location_names_only`; added
`test_build_render_messages_system_message_has_full_character_and_location_details`,
`test_build_render_messages_system_roster_includes_unassigned_characters_and_locations`, and
`test_build_render_messages_scene_message_sections_appear_in_requested_order` (asserts the exact
`# Scene: {heading}` → `## Length` → `## Description` → `## Locations` → `## Characters` →
`## Required Elements` order via string-index comparisons, using the renamed heading).
`pdm run pytest` (391 passed) and `pdm run lint` both pass.

## Rationale

The developer is iterating on the rendering agent's prompt through their own hands-on testing of
generated prose quality, driving each of these changes directly: (1)-(3) initial fiction framing
and cleanup, later revising the closing instruction's wording entirely to explain the scene-by-
scene authoring process and emphasize "required elements" as the story's continuity spine;
(4)-(5) giving the whole system prompt one consistent markdown structure and moving full
character/location detail to a canonical system-prompt roster instead of repeating it on every
scene message; (6) applying that same markdown structure to the per-scene message, in an
explicit field order the developer specified, and renaming "Required Actions" to "Required
Elements" in the prompt text specifically (matching the new suffix wording) while explicitly
deferring the same rename everywhere else in the app (data field name, GUI labels) to a later
pass. The developer will keep testing and iterating on prompt wording and structure; this
encounter records all concrete changes made so far.

## Log

### Review - 2026-08-22T15:29:32Z - John Hoff

Reviewed against the two applicable world lore items (linting, unit-testing): the encounter's Requirements record `pdm run lint` and `pdm run pytest` (391 passed) both passing, and a spot-check of `src/scene/agent/rendering.py` and `test/scene/agent/test_rendering.py` confirms the described markdown-restructuring changes and matching new/updated tests are actually present, correctly mirrored under `test/`, and within the 120-character line limit (one line lands exactly at 120). No conflicts with either lore item. As expected for an unscripted encounter, the pytest/lint results are recorded rather than independently reproduced here, and the untouched status of the out-of-region `src/scene/cli/render_app.py` is taken on the encounter's own assertion — both noted as unverified-but-low-risk rather than defects. PASS-WITH-NOTES.

### Completed - 2026-08-22T15:29:42Z - John Hoff

Recorded and reviewed prompt-restructuring work: fiction-framing prefix/suffix, markdown-headed Scenario/Style Guidance/Characters/Locations system-prompt sections, and a restructured per-scene message (title, Length, Description, Locations, Characters, Required Elements). All verified via pdm run lint and pdm run pytest (391 passed).
