---
archived: false
created_by: John Hoff
created_on: '2026-08-28T21:00:41Z'
name: c009-post-v2-polish
status: open
updated_by: John Hoff
updated_on: '2026-08-28T21:00:43Z'
---

# Post-v2 polish

## Purpose

General usability, quality, and maintainability improvements to Scene
Writer now that the data-model-v2 refactor (`c008-story-data-model-v2`) has
landed and its impact is being felt in day-to-day usage. Unlike prior
campaigns, this one is not scoped to a single design document — it's an
ongoing home for polish-sized work discovered while using the app: rough
edges, developer-experience friction, small refactors, and configuration/
tooling improvements that don't warrant their own campaign.

## Scope

Open-ended. Encounters under this campaign are individually scoped in their
own `Requirements`/`Rationale`/`Plan`. Expect a mix of regions (`data`,
`core`, `agent`, `cli`, `gui`) depending on what each encounter addresses.

## Notes

- Existing lore (`linting`, `unit-testing`) applies throughout: ruff-clean,
  120-char lines, and pytest coverage for new/changed code before any
  encounter is marked complete.
- Encounters here are expected to be smaller and more independent than a
  typical feature campaign's — most should have few or no dependencies on
  each other.
