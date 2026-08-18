---
created_by: John Hoff
created_on: '2026-08-18T01:47:46Z'
name: cli
path: src/scene/cli
summary: Collection of standalone CLI programs (built with Typer), each its own console
  script, driving either an agent or direct CRUD against scene.core.
updated_by: John Hoff
updated_on: '2026-08-18T04:27:08Z'
---

# CLI

CLI entry points for the project, each registered as its own console script (e.g. `scene-data`) and built with `typer`. Some CLI programs drive an agent from `scene.agent`; others, like `scene-data`, provide direct CRUD access to persisted data with one Typer sub-command group per entity (e.g. `scene-data story ...`). All CLI programs read and write scene state through `scene.core`'s shared service layer rather than talking to `scene.data` directly. Intended as the primary interface until the GUI exists.
