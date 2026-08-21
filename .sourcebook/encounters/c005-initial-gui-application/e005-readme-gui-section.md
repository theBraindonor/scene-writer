---
archived: false
campaign: c005-initial-gui-application
created_by: John Hoff
created_on: '2026-08-20T22:47:39Z'
depends_on:
- e004-chat-panel-integration
kind: scripted
name: e005-readme-gui-section
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-21T04:09:43Z'
---

# E005 — README GUI Section

## Requirements
- Update `README.md` to document the new `scene-writer` GUI: a PySide6 desktop application with
  a collapsible story-picker sidebar, a main entity column (full view/create/edit/delete for a
  story's scenes, cast, locations, and their assignments, plus the story's own title/scenario/
  style guidance), a read-only rendering column showing the selected scene's active rendering,
  and a full-width chat panel at the bottom driving the same coordinating agent as
  `scene-coordinator chat`.
- Note that the GUI's rendering column is view-only for now — generating or regenerating prose
  is still done via `scene-coordinator render` — so a reader doesn't expect generation from the
  new command.
- Note that direct edits in the entity column and edits made through the chat panel go through
  the same underlying data layer, so either way of working stays consistent with the other.
- Do not add integration-style tests or any other test coverage for this change — it is a
  documentation-only update with no code behavior to verify, consistent with `c002`/`c003`/
  `c004`'s equivalent README encounters.

## Rationale
Closes out this campaign the way `c002`, `c003`, and `c004` each closed with their own README
encounter: once the GUI's full first-version scope (`e001`–`e004`) exists, the README should
tell a new contributor it exists, roughly what it does, and how it relates to the existing CLIs,
without duplicating detail that belongs in code.

## Plan
1. In `README.md`, add a section introducing `scene-writer` (near the existing
   `scene-coordinator chat`/`render` sections), covering the sidebar, entity column, rendering
   column, and chat panel per Requirements.
2. Review the rest of the README for anything now stale given this campaign's changes (e.g. the
   `src/scene/gui` project-layout bullet, which currently says "not yet implemented") and adjust
   wording minimally.
3. Run `pdm run lint` and confirm zero errors (no source files are touched, but this keeps the
   verification step consistent with the rest of the campaign).

## Verification
- Manually review the rendered `README.md` and confirm the new section reads clearly and
  accurately reflects the shipped GUI.
- Run `pdm run lint` and confirm zero errors.

## Log

### Review - 2026-08-21T04:08:17Z - John Hoff

Reviewed e005-readme-gui-section (scripted, draft) against the two applicable lore items (linting, unit-testing) using README.md, the encounter body, the gui region, and both lore bodies. The Plan satisfies linting by running `pdm run lint` in both the Plan and Verification steps, and correctly omits test coverage per the unit-testing lore, which only governs new/modified code — this is a documentation-only change with none, and Requirements explicitly call out this precedent from c002/c003/c004's equivalent README encounters. No lore conflicts found; the Plan concretely names its target file and enumerates the required documentation points plus a staleness pass over the rest of the README. PASS-WITH-NOTES.

### Completed - 2026-08-21T04:09:43Z - John Hoff

Added a scene-writer GUI section to README.md (sidebar/entity column/rendering column/chat panel, view-only rendering column note, shared-data-layer note), updated the intro paragraph and the src/scene/gui project-layout bullet to no longer call the GUI "planned"/"not yet implemented". pdm run lint passes with zero errors. Developer reviewed the rendered README and confirmed it reads accurately.
