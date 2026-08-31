---
archived: false
created_by: John Hoff
created_on: '2026-08-30T20:38:53Z'
name: c010-application-agent
status: completed
updated_by: John Hoff
updated_on: '2026-08-31T05:10:04Z'
---

## Purpose

Implement the GUI's application agent, as designed in `docs/application-agent.md`:
a conversational agent that replaces the coordinator inside the GUI and operates the
application itself (opening stories, switching tabs, selecting/creating scenes, editing
records, and triggering renders) rather than editing rows by id. The CLI's coordinator is
unaffected — this campaign is GUI-only.

## Scope

Encounters under this campaign implement the tool catalog and interaction rules laid out
in `docs/application-agent.md`: the direct-entity tools for Story/Characters/Locations,
the stateful select-then-act pattern for Scenes (including `render_scene`), and wiring
the GUI's chat surface to this new agent in place of the coordinator. Expect regions
`gui` and `agent` primarily, with `core`/`data` touched only if a needed query doesn't
already exist there.

Out of scope, per the design doc: rendering version history/activation, full-story
render/export/import, and window-chrome actions stay manual-only and are not to be
exposed as agent tools by this campaign's encounters.

## Notes

- Existing lore (`linting`, `unit-testing`) applies throughout: ruff-clean, 120-char
  lines, and pytest coverage for new/changed code before any encounter is marked
  complete.
- `docs/application-agent.md` is living documentation for this campaign, alongside
  `docs/data-model.md`/`docs/data-model-v2.md` and `docs/prompt-guidance.md` — all three
  are meant to help people understand the application, not just record a one-time design.
  Whenever an encounter's implementation deviates from what the document currently says
  (a tool gains/loses a parameter, a boundary changes, a rule turns out to work
  differently in practice), update the document as part of that encounter rather than
  letting it drift: add or correct the affected section, or append a dated note where a
  clean rewrite isn't warranted. The document should stay an accurate guide to the
  application agent as built, not just as originally planned.

## Log

### Completed - 2026-08-31T05:10:04Z - John Hoff

All four planned encounters landed: e017 introduced the application agent and wired it into the GUI's chat panel for the direct-entity tier (Story/Characters/Locations), e018 added scene selection/CRUD state and the select-then-act pattern, e019 added render_scene, and e020 (an unplanned but valuable follow-up from live use) fixed markdown rendering and input focus in the chat panel. The CLI's coordinator was left untouched throughout, as scoped. docs/application-agent.md was kept in sync with implementation deviations along the way (e.g. the story_id-omission rationale, generation_guidance/generation_guideance translation). No scope items were dropped; the only deviations were small implementation-level fixes (e.g. QTextEdit -> QTextBrowser in e020), each logged on its encounter. Full pytest/lint gates passed throughout, and manual GUI smoke tests confirmed the agent driving tab switches, selection, and rendering as designed.
