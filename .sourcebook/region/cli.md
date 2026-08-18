---
created_by: John Hoff
created_on: '2026-08-18T01:47:46Z'
name: cli
path: src/scene/cli
summary: Collection of standalone CLI programs, each driving one agent in the two-phase
  scene generation pipeline (construction and drafting).
updated_by: John Hoff
updated_on: '2026-08-18T01:49:40Z'
---

# CLI

CLI entry points for the project. Each command wraps one agent from `scene.agent` and reads/writes scene state through `scene.data`. Intended as the primary interface until the GUI exists.
