---
archived: false
campaign: c002-initial-data-model-and-crud
created_by: John Hoff
created_on: '2026-08-18T13:42:18Z'
depends_on: []
kind: scripted
name: e006-readme-data-model-section
regions:
- cli
- core
- data
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T13:45:18Z'
---

# E006 — README Data Model Section

## Requirements
- Add a "Data model" section to `README.md` giving a brief, high-level introduction to the persisted entities (story, scene, rendering, character, location, and the scene cast/location join tables) and linking to `docs/data-model.md` as the formal source of truth, rather than duplicating or enumerating every column/constraint/CLI command in the README.
- Update the README's closing CLI example, which currently only demonstrates `scene-data story --help`, to point at `scene-data --help` (or otherwise make clear that `story` is one of several `scene-data` sub-command groups) so the README doesn't read as if `story` is the only manageable entity.
- Do not add integration-style tests or any other test coverage for this change — it is a documentation-only update with no code behavior to verify.

## Rationale
`c002-initial-data-model-and-crud`'s five encounters (`e001`–`e005`) delivered full model/service/CLI coverage for every entity in `docs/data-model.md`, but `README.md` still only mentions the `story` CLI group from `e001` and has no pointer to the data model document at all. A new contributor reading the README currently has no way to discover that scene, rendering, character, location, and the two join tables are also fully implemented, or where the schema itself is documented. This is a small, doc-only encounter to close that gap with a brief pointer rather than a full command reference, per explicit direction to keep the README light and defer to `docs/data-model.md` for detail.

## Plan
1. In `README.md`, add a new "Data model" section (after "Project layout", before "Development") with 2-4 sentences introducing the persisted entities at a high level (a story contains scenes, each scene may have renderings plus assigned characters/locations) and a link to `docs/data-model.md` for the full schema.
2. Update the README's final CLI example from `pdm run scene-data story --help` to `pdm run scene-data --help`, so it reflects the full set of sub-command groups (`story`, `scene`, `rendering`, `character`, `location`, `scene-character`, `scene-location`) rather than singling out `story`.

## Verification
- Manually review the rendered `README.md` (e.g. via a Markdown preview or `pdm run scene-data --help`'s actual output) and confirm the new section reads clearly, the link to `docs/data-model.md` resolves to the correct file, and the CLI example is accurate.
- Run `pdm run lint` and confirm zero errors (no source files are touched, but this keeps the verification step consistent with the rest of the campaign).

## Log

### Review - 2026-08-18T13:44:33Z - John Hoff

Plan reviewed against the two applicable world-level lore items, linting and unit-testing, and both are honored: the Verification step re-runs pdm run lint despite no source files changing, and the Requirements section correctly and explicitly scopes out test coverage since this is a doc-only change with no modified code. The Plan's target edits (a new "Data model" section between "Project layout" and "Development," and replacing the pdm run scene-data story --help closing example) match the current README.md structure, and the referenced docs/data-model.md exists. One non-blocking note: the encounter is assigned to the cli/core/data regions, but its only edit target, README.md, sits outside all three of those paths — worth a second look, though it didn't affect the applicable-lore resolution here.

### Completed - 2026-08-18T13:45:18Z - John Hoff

Verified: added a "Data model" section to README.md giving a brief overview of story/scene/rendering/character/location relationships with a link to docs/data-model.md; replaced the closing CLI example with pdm run scene-data --help, whose actual output correctly lists all seven sub-command groups (story, scene, rendering, character, scene-character, location, scene-location). pdm run lint reports zero errors. No tests added, per Requirements — doc-only change.
