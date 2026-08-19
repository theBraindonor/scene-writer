---
archived: false
campaign: c004-scene-rendering-agent
created_by: John Hoff
created_on: '2026-08-19T00:52:39Z'
depends_on:
- e003-render-regenerate-and-versions
kind: scripted
name: e004-readme-render-cli-section
regions:
- cli
status: completed
updated_by: John Hoff
updated_on: '2026-08-19T16:18:17Z'
---

# E004 — README Render CLI Section

## Requirements
- Update `README.md` to document the new `scene-coordinator render` CLI: a non-interactive, LLM-driven Textual TUI that generates each scene's prose in order (or regenerates a specific scene), using the story's structural data and prior scenes' active renderings as context — no story id argument; an in-TUI picker selects the story. Briefly mention the two-pane layout (scene list/detail, rendering output), the "render next scene"/"regenerate this scene" actions, and in-TUI browsing/activation of a scene's rendering versions.
- Note that the rendering agent's LLM connection is configured the same way as the coordinating agent's (`models.yaml`/`.env`), but via the separate `SCENE_RENDERING_AGENT` role selector — i.e. the two agents can be pointed at different models independently, closing the loop on the seam `c003-coordinating-agent` reserved but never consumed.
- Do not add integration-style tests or any other test coverage for this change — it is a documentation-only update with no code behavior to verify, consistent with `c002-initial-data-model-and-crud`'s and `c003-coordinating-agent`'s equivalent README encounters.

## Rationale
Closes out this campaign the same way `c002` and `c003` each closed with their own README
encounter: once the render TUI's full scope (`e002`/`e003`) exists, the README should tell a
new contributor it exists, roughly what it does, and that it's a second, independently
configured agent role, without duplicating detail that belongs in code/config.

## Plan
1. In `README.md`, add a brief section (near the existing `scene-coordinator chat` mention added in `c003`/`e009`) introducing `scene-coordinator render`, its no-story-id in-TUI picker, two-pane layout, render-next/regenerate actions, and version browsing.
2. Note the `SCENE_RENDERING_AGENT` role selector alongside the existing `SCENE_COORDINATING_AGENT` mention, clarifying the two agents can run on independently configured models.
3. Review the rest of the README for anything now stale given this campaign's changes and adjust wording minimally if needed.
4. Run `pdm run lint` and confirm zero errors (no source files are touched, but this keeps the verification step consistent with the rest of the campaign).

## Verification
- Manually review the rendered `README.md` and confirm the new section reads clearly and accurately reflects the shipped CLI.
- Run `pdm run lint` and confirm zero errors.

## Log

### Review - 2026-08-19T14:03:57Z - John Hoff

Plan is well-scoped and consistent with lore: linting is explicitly verified via `pdm run lint`, and the deliberate omission of unit tests is justified as a documentation-only change, mirroring the real precedent already visible in README.md from prior README-only encounters (`e009`'s `scene-coordinator chat` section, including the exact 'reserved for a future rendering agent' sentence this encounter plans to update). Minor observation: the encounter is assigned to the `cli` region while its actual edit target, README.md, sits outside that region's path — consistent with the apparent convention from `e009` but worth noting. No lore conflicts found; the accuracy of the described render-TUI behavior against the shipped e002/e003 implementation is left for the encounter's own manual Verification step, as it falls outside this review's bounded reading surface.

### Completed - 2026-08-19T16:18:17Z - John Hoff

README.md now documents scene-coordinator render (two-pane layout, in-TUI story picker, render-next/regenerate, version browsing, escape-to-cancel) and the SCENE_RENDERING_AGENT role selector alongside SCENE_COORDINATING_AGENT. pdm run lint clean; manually reviewed the rendered README for clarity and accuracy against the shipped CLI.
