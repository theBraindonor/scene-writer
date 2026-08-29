---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-29T02:07:41Z'
depends_on: []
kind: scripted
name: e002-rendering-prompt-structure
regions:
- agent
status: completed
updated_by: John Hoff
updated_on: '2026-08-29T03:24:28Z'
---

# Restructure the rendering agent's prompt with headings, field intent, and closing rules

## Requirements

- Fix the rendering (scene-drafting) agent's system prompt so the character
  and location reference cards are no longer visually nested under the
  `## Generation Guidance` heading: each reference block gets its own
  heading, `## Cast of Characters` and `## Locations`, added after
  `## Generation Guidance` in `build_render_messages`
  (`src/scene/agent/rendering.py`).
- Use one consistent heading format across both the system prompt and the
  user turn. Today the system prompt uses markdown `## Heading` style while
  the user turn uses plain all-caps labels (`CURRENT CANON`,
  `OPTIONAL RECENT PROSE`, `SCENE BRIEF`) with no markdown. Convert the user
  turn's labels to the same `## Heading` style so the whole prompt reads as
  one consistent document.
- Give the model an explicit understanding of what the scene-brief fields
  intend, using the clarification already agreed in
  `docs/prompt-guidance.md`'s "Scene-specific request" section: "`required_actions`
  describes events or beats that must occur. `desired_outcome` describes what
  should be different at the end of the scene. They are complementary." Add
  this (or a faithful paraphrase) as a short caption immediately under the
  new `## Scene Brief` heading, before its field lines.
- Add the standing generation rules that `docs/prompt-guidance.md`'s
  "Scene-writing prompt template" section already specifies but that the
  current implementation never wired in, as a new `## Requirements` section
  in the system prompt (placed after the existing fiction-framing prompt and
  before `## Story Brief`):
  - Use the requested point of view and tense.
  - Dramatize through action, sensory detail, dialogue, and interiority.
  - Do not resolve a major plot thread unless the scene brief explicitly requires it.
  - Do not introduce new named characters, world rules, abilities, or backstory facts unless the scene brief authorizes them.
  - End at a meaningful turn, decision, revelation, complication, or emotional shift.
  - Return fiction prose only. Do not explain your process or restate these materials.
- Append a final closing-instructions paragraph to the user turn, after the
  `## Scene Brief` section (present regardless of whether Current
  Canon/Recent Prose are included), establishing priority order: satisfying
  the Scene Brief's required actions and desired outcome is the primary
  objective; Current Canon is the authoritative record of established
  facts; Optional Recent Prose is for tone/pacing only, never a source of
  new facts; the Scene Brief's requirements take precedence if anything
  conflicts.
- All new prompt prose (the requirements bullets, the scene-brief caption,
  the closing instructions) lives in `agent-prompts.yaml` under a `rendering`
  section, loaded through the existing `load_prompts()` (from
  `e001-agent-prompts-config`) rather than hardcoded in Python — consistent
  with how `fiction_prefix`/`fiction_suffix` are already externalized.
- No change to the coordinator or continuity-editor prompts, and no change
  to which data feeds the rendering prompt (still story brief, style
  guidance, generation guidance, assigned characters/locations, preceding
  continuity snapshot, preceding active rendering, and the target scene's
  fields) — this is a structural/content-clarity change to the same
  existing prompt, not a new data source.

## Rationale

The user reported that the character/location reference cards visually read
as part of `## Generation Guidance` since they're appended with no heading
of their own, and asked for a consistent heading format between the system
and user portions of the rendering prompt, plus explicit rules that keep
generation anchored to the scene brief. Separately, `docs/prompt-guidance.md`
(the aspirational design doc from `c008-story-data-model-v2`) already
specifies a "Requirements" rule list for the scene-writing prompt template
and an explanation of how `required_actions`/`desired_outcome` relate — content
that was never implemented in `src/scene/agent/rendering.py`. This encounter
folds that already-agreed-but-unimplemented content in alongside the
requested structural fix, rather than inventing new prompt copy from
scratch. Per `c008`'s own notes, the doc is "guidance for intent, not a
contract to match line-for-line," so headings are adapted to `##` markdown
(matching the system prompt's existing style) rather than the doc's literal
all-caps template.

## Plan

1. Add four new fields to `agent-prompts.yaml`'s `rendering` section and to
   `PromptSet`/`load_prompts()` in `src/scene/agent/prompts.py`:
   - `requirements`: a YAML list of the six rule strings above, exposed as
     `PromptSet.rendering_requirements: tuple[str, ...]`.
   - `scene_brief_caption`: the required_actions/desired_outcome
     clarification, exposed as `PromptSet.rendering_scene_brief_caption: str`.
   - `closing_instructions`: the final priority paragraph, exposed as
     `PromptSet.rendering_closing_instructions: str`.
   Validate `requirements` is a non-empty list of non-empty strings (new
   loader helper alongside the existing scalar-field validator); validate
   `scene_brief_caption`/`closing_instructions` with the existing
   string-field validator. Update the file's header comment to describe the
   new keys.
2. In `src/scene/agent/rendering.py`, add small helpers:
   - `_headed(heading: str, body: str) -> str` returning
     `f"## {heading}\n\n{body}"`, replacing the ad hoc `f"## Story
     Brief\n\n{...}"`-style string building used today.
   - A `_requirements_section(requirements: tuple[str, ...]) -> str` that
     renders `"## Requirements\n\n" + "\n".join(f"- {item}" for item in
     requirements)`.
3. Rework `build_render_messages` to:
   - Build `system_lines` as: `fiction_prefix`,
     `_requirements_section(prompts.rendering_requirements)`,
     `_headed("Story Brief", story.story_brief)`, then the existing
     conditional Style/Generation Guidance lines via `_headed(...)`, then a
     conditional `_headed("Cast of Characters", ...)` built from
     `list_characters_for_scene` (only when non-empty), then a conditional
     `_headed("Locations", ...)` built from `list_locations_for_scene` (only
     when non-empty), then `fiction_suffix`. Remove the now-unused
     `_scene_reference_cards` helper (its two responsibilities move inline
     since they need independent headings).
   - Rename `_scene_brief_text` to `_scene_brief_fields_text` and drop its
     leading `"SCENE BRIEF"` line (the heading is now added by the caller);
     keep its field lines (`Heading`, `Point of view`, `Brief`, `Required
     actions`, `Desired outcome`, `Target length`) exactly as they are today.
   - Build the Scene Brief's body as
     `f"{prompts.rendering_scene_brief_caption}\n\n{_scene_brief_fields_text(session, target)}"`
     and wrap it with `_headed("Scene Brief", ...)`.
   - Change `user_sections` to use `_headed("Current Canon", ...)` and
     `_headed("Optional Recent Prose", ...)` instead of the current
     `"CURRENT CANON\n\n..."`/`"OPTIONAL RECENT PROSE\n\n..."` string
     literals.
   - Always append `prompts.rendering_closing_instructions` as the final
     user-turn section, after the Scene Brief section (regardless of
     whether Current Canon/Recent Prose were included).
4. Update `test/scene/agent/test_rendering.py` for the new literal text:
   `"SCENE BRIEF"` → `"## Scene Brief"`, `"CURRENT CANON"` → `"## Current
   Canon"`, `"OPTIONAL RECENT PROSE"` → `"## Optional Recent Prose"`
   throughout. Add new assertions covering: `## Requirements` appears in the
   system message and precedes `## Story Brief`; `## Cast of Characters` and
   `## Locations` each appear as their own heading (not folded into
   Generation Guidance) when characters/locations are assigned, and are
   both absent when none are assigned; the scene-brief caption text appears
   in the user message; the closing-instructions text appears in the user
   message after the Scene Brief content, including in the no-prior-scenes
   case.
5. Update `test/scene/agent/test_prompts.py` to cover the three new
   `PromptSet` fields: successful load of `rendering_requirements` (as a
   tuple) / `rendering_scene_brief_caption` / `rendering_closing_instructions`;
   a non-list or empty `requirements` value raises; a `requirements` list
   containing a blank string raises; a missing/empty `scene_brief_caption`
   or `closing_instructions` raises.
6. Run `pdm run lint` and `pdm run pytest`, fixing anything flagged.

## Verification

- `pdm run lint` passes with no errors.
- `pdm run pytest` passes, including the updated `test_rendering.py` and
  `test_prompts.py` cases and the full existing suite.
- Manually inspect a `build_render_messages` call's rendered system and
  user message strings (e.g. via a quick `pdm run python -c` script against
  an in-memory SQLite session) to visually confirm: `## Requirements`
  appears before `## Story Brief`; `## Cast of Characters` and
  `## Locations` are distinct headings, not nested under
  `## Generation Guidance`; the user turn's `## Current Canon` /
  `## Optional Recent Prose` / `## Scene Brief` headings match the system
  prompt's `##` style; the scene-brief caption and closing-instructions
  paragraph both appear where intended.
- `git grep` confirms no remaining `"CURRENT CANON"`, `"OPTIONAL RECENT
  PROSE"`, or `"SCENE BRIEF"` all-caps literals in `src/scene/agent/rendering.py`.

## Log

### Review - 2026-08-29T02:10:39Z - John Hoff

This scripted encounter is reviewable and consistent with the two applicable lore items (linting, unit-testing): the Plan commits explicitly to a clean pdm run lint and a fully-passing pdm run pytest before completion, and its test-file updates to test/scene/agent/test_rendering.py and test/scene/agent/test_prompts.py correctly mirror the modified src/scene/agent/rendering.py and src/scene/agent/prompts.py, with concrete new assertions covering every new prompt element (Requirements section placement, distinct Cast of Characters/Locations headings, scene-brief caption, closing-instructions ordering) and validation failure modes for the new YAML fields. The encounter's citation of docs/prompt-guidance.md checks out verbatim against both the "Scene-specific request" clarification and the "Scene-writing prompt template" Requirements bullets, and its own framing of the doc as intent-guidance rather than a literal-format contract is a reasonable basis for adapting the doc's plain-label headings to the codebase's existing ##-markdown convention. Cross-referencing the current src/scene/agent/rendering.py and its tests confirms the encounter's premise (unheaded reference cards, inconsistent heading styles) is accurate and that the Plan's literal-replacement list is complete. No lore conflicts or scope gaps were found within the bounded reading surface.

### Message - 2026-08-29T02:43:19Z - John Hoff

Interactive testing during implementation surfaced two refinements to the planned structure, both still within this encounter's scope (consistent headings + closing rules for the rendering prompt): (1) the model tends to over-resolve/wrap up a scene well past its desired outcome, since it doesn't otherwise know another scene follows — the user-turn closing paragraph (previously unheaded `closing_instructions`) is now wrapped in a new `## Final Instructions` heading and its content extended to explicitly instruct stopping once the required actions/desired outcome are reached, without adding a tidy conclusion/resolution/epilogue, since the narrative continues in a following scene. (2) the system prompt's trailing `fiction_suffix` content (placed after Locations) is now similarly wrapped in a new `## Scene Generation Instructions` heading — renamed to `scene_generation_instructions` in agent-prompts.yaml/PromptSet — with an added sentence explicitly previewing that the next message will contain this scene's brief plus any current canon/recent prose, so the model is prepped for what follows. No other structural changes; all four existing headings (Requirements, Story Brief/Style/Generation Guidance, Cast of Characters, Locations, Current Canon, Optional Recent Prose, Scene Brief) are unchanged.

### Completed - 2026-08-29T03:24:28Z - John Hoff

Implemented as planned, with two refinements recorded and applied during implementation (see prior message log entry): the system prompt now has ## Requirements (doc-sourced generation rules), ## Story Brief/Style Guidance/Generation Guidance, ## Cast of Characters and ## Locations as their own headings, and ## Scene Generation Instructions (renamed from fiction_suffix, previewing that the next message contains the scene brief). The user turn now uses ## Current Canon / ## Optional Recent Prose / ## Scene Brief (with the required_actions/desired_outcome caption) and ## Final Instructions (priority ordering plus explicit anti-wrap-up guidance so the model doesn't resolve the scene past its desired outcome, since further scenes follow). All new prompt prose lives in agent-prompts.yaml via PromptSet/load_prompts(). 487 tests pass, lint is clean, and the rendered system/user messages were manually inspected end-to-end to confirm the structure matches the design.
