---
assigned_lore:
- linting
- unit-testing
created_by: John Hoff
created_on: '2026-08-18T01:32:11Z'
name: scene-writer
schema_version: 1
updated_by: John Hoff
updated_on: '2026-08-18T01:53:35Z'
---

# Scene Writer

Scene Writer is an agentic scene-writing tool built around a two-phase generation pipeline:

1. **Scene Construction** — establishes the overall details of a scene (setting, characters, goals, constraints, etc.) before any prose is generated.
2. **Scene Drafting** — incrementally builds the scene's prose, using the construction-phase details together with the output of previously generated scenes for continuity.

All scene definitions and generated output are persisted to a local SQLite database. The project ships as a collection of standalone CLI programs, each driving one agent in the pipeline, with the long-term goal of layering a unified GUI on top of these CLI-driven building blocks.
