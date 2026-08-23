---
archived: false
created_by: John Hoff
created_on: '2026-08-22T04:50:44Z'
name: c007-rendering-prompt-quality
status: completed
updated_by: John Hoff
updated_on: '2026-08-23T22:26:01Z'
---

# C007 — Rendering Prompt Quality

## Scope

Iterative refinement of the scene-rendering agent's system prompt (`build_render_messages` in
`src/scene/agent/rendering.py`), driven by the developer's own hands-on testing of generated
prose quality against locally-configured models. Kept as its own campaign rather than folded
into `c006-gui-usability` because it changes `scene.agent`, which `c006` explicitly excludes
("no changes to `scene.core`/`scene.data`/`scene.agent`... not on adding new raw story-domain
functionality").

Out of scope: any GUI, CLI, or TUI surface change (`c006` and the existing TUI/CLI already cover
those) and any change to the rendering pipeline's mechanics (message assembly order, streaming,
persistence) — this campaign is specifically about the *content* of the instructions given to
the LLM, not how the pipeline invokes it.

## Log

### Completed - 2026-08-23T22:26:01Z - John Hoff

Delivered a full markdown restructuring of the scene-rendering agent's prompt (e001-fictional-framing-prefix): a fiction-framing prefix and rewritten closing suffix explaining the scene-by-scene authoring process and the role of "required elements" as the story's continuity spine; consistent `## Heading` markdown treatment across Scenario, Style Guidance, and two new system-prompt rosters (Characters, Locations) sourced from the full story-wide character/location lists; and a restructured per-scene message (title, Length, Description, Locations, Characters, Required Elements) with character/location detail moved out of the per-scene message and into the canonical system-prompt rosters. Closing the campaign now, with the developer's direction that a fair amount of hands-on testing has been completed and the project is moving to an application-wide refactoring pass next. Further prompt-quality iteration identified later can open a new campaign when that work resumes.
