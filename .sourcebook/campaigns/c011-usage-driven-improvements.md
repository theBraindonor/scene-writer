---
archived: false
created_by: John Hoff
created_on: '2026-08-31T06:19:34Z'
name: c011-usage-driven-improvements
status: open
updated_by: John Hoff
updated_on: '2026-08-31T06:20:44Z'
---

## Purpose

With `c010-application-agent` complete, the application (CLI pipeline + GUI + application agent)
is in a state where it can sustain heavier day-to-day use. This campaign is the ongoing home for
general improvements, fixes, and refinements surfaced by that real usage, rather than a single
scoped feature.

## Scope

Any region (`agent`, `cli`, `core`, `data`, `gui`) may be touched, as needed by whatever usage
surfaces. There is no fixed feature list for this campaign up front — encounters are added
incrementally as issues or gaps are found while actually using the application.

**Every encounter under this campaign must ground its Rationale in direct, first-hand usage of
the application** — a specific friction point, bug, missing capability, or rough edge hit while
actually running the CLI pipeline or the GUI (ideally via the `run` skill or a live session), not
a speculative "this would probably be nice" improvement or a hypothetical future need. If an
encounter's Rationale can't point to a concrete usage moment that motivated it, it doesn't belong
in this campaign yet — wait until it's actually been hit.

## Notes

- Existing lore (`linting`, `unit-testing`) applies throughout: ruff-clean, 120-char lines, and
  pytest coverage for new/changed code before any encounter is marked complete.
- Because scope is discovered incrementally rather than planned up front, expect this campaign to
  stay open for an extended period, accumulating encounters one at a time as usage continues.
