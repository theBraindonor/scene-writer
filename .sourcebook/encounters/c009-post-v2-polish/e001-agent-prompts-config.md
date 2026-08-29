---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-28T21:01:03Z'
depends_on: []
kind: scripted
name: e001-agent-prompts-config
regions:
- agent
status: completed
updated_by: John Hoff
updated_on: '2026-08-29T01:50:54Z'
---

# Extract agent prompts into a tracked YAML config

## Requirements

- Move the three hardcoded agent-prompt strings out of Python source and
  into a new `agent-prompts.yaml` file at the project root, so all of the
  agents' prompts are visible and editable in one place:
  - the coordinating agent's system prompt (`DEFAULT_SYSTEM_PROMPT` in
    `src/scene/agent/coordinator/loop.py`)
  - the continuity-editing agent's system prompt
    (`CONTINUITY_EDITOR_SYSTEM_PROMPT` in `src/scene/agent/continuity.py`)
  - the rendering (scene-drafting) agent's fiction framing text — the
    `fiction_prefix` and `fiction_suffix` strings built inline inside
    `build_render_messages` in `src/scene/agent/rendering.py`
- Add a small loader module, `src/scene/agent/prompts.py`, mirroring the
  existing `src/scene/agent/registry.py` (which loads `models.yaml`): a
  frozen dataclass holding the loaded prompt strings, plus a
  `load_prompts(prompts_path: Path | None = None) -> PromptSet` function
  defaulting to the project-root `agent-prompts.yaml`, raising a clear
  `RuntimeError`/`TypeError` if the file is missing or malformed.
- Unlike `models.yaml` (gitignored, user-supplied from
  `models.example.yaml`), `agent-prompts.yaml` **must be tracked in git** —
  do not add it to `.gitignore`. It ships with the real prompt content the
  app already uses, not placeholder/example values.
- Wire the three call sites (`loop.py`, `continuity.py`, `rendering.py`) to
  source their prompt text from `load_prompts()` instead of the inline
  string literals, preserving the exact existing prompt wording so agent
  behavior is unchanged.
- Preserve the existing public names call sites already import
  (`DEFAULT_SYSTEM_PROMPT` from `loop.py`, used by
  `src/scene/cli/coordinator_app.py` and `src/scene/gui/chat_panel.py`;
  `CONTINUITY_EDITOR_SYSTEM_PROMPT` from `continuity.py`) so no other module
  needs to change.

## Rationale

Agent prompts are currently scattered as inline Python string literals
across three different modules, making them hard to find, read as a whole,
or tweak without touching code. `models.yaml` already established the
pattern of externalizing per-role configuration next to the project root
with a small typed loader in `scene.agent`; prompts are natural to manage
the same way. This is polish/maintainability work, not a behavior change —
prompt wording stays identical, just relocated.

## Plan

1. Read the exact current text of `DEFAULT_SYSTEM_PROMPT`,
   `CONTINUITY_EDITOR_SYSTEM_PROMPT`, and rendering.py's `fiction_prefix`/
   `fiction_suffix` to ensure verbatim transcription.
2. Create `agent-prompts.yaml` at the project root with a top-level mapping
   keyed by role (`coordinator`, `continuity_editor`, `rendering`), each
   holding its prompt string(s) as YAML block scalars, plus a short header
   comment (mirroring `models.example.yaml`'s style) explaining the file's
   purpose and that, unlike `models.yaml`, it's tracked in git.
3. Add `src/scene/agent/prompts.py` with a `PromptSet` frozen dataclass and
   `load_prompts()` function that reads and validates the YAML (missing
   file, malformed structure, missing/empty fields all raise clearly),
   following `registry.py`'s existing conventions.
4. Update `src/scene/agent/coordinator/loop.py` to set
   `DEFAULT_SYSTEM_PROMPT = load_prompts().coordinator_system_prompt` (or
   equivalent) instead of the inline literal.
5. Update `src/scene/agent/continuity.py` similarly for
   `CONTINUITY_EDITOR_SYSTEM_PROMPT`.
6. Update `src/scene/agent/rendering.py`'s `build_render_messages` to source
   `fiction_prefix`/`fiction_suffix` from the loaded prompt set instead of
   inline literals.
7. Add `test/scene/agent/test_prompts.py` covering `load_prompts()`:
   resolves all fields from a well-formed file, missing-file error,
   malformed-structure error, and missing/empty-field error — mirroring
   `test/scene/agent/test_registry.py`'s test shapes.
8. Confirm no existing test asserts against the literal old prompt text in
   a way that would break (checked: `test_rendering.py` and
   `test_continuity.py` only assert on story/scene data substrings, not the
   hardcoded framing text).
9. Run `pdm run lint` and `pdm run pytest` and fix anything they flag.

## Verification

- `pdm run lint` passes with no errors.
- `pdm run pytest` passes, including new `test_prompts.py` cases and the
  full existing suite (particularly `test_rendering.py`,
  `test_continuity.py`, `test/scene/agent/coordinator/test_loop.py`).
- `agent-prompts.yaml` exists at the project root, is *not* listed in
  `.gitignore`, and `git status`/`git diff` show it as a new tracked file
  (not ignored).
- Manually diff the YAML's prompt strings against the original inline
  Python literals (e.g. a quick `python -c` load-and-print) to confirm the
  wording is byte-for-byte unchanged.
- `git grep` for the old constant literals in `loop.py`, `continuity.py`,
  and `rendering.py` turns up no leftover hardcoded prompt text — only the
  `load_prompts()`-sourced values remain.

## Log

### Review - 2026-08-28T21:03:21Z - John Hoff

Encounter e001-agent-prompts-config reviewed against the two applicable lore items (linting, unit-testing), both satisfied: the Plan explicitly runs `pdm run lint` and gates completion on a clean result (step 9, Verification), and adds `test/scene/agent/test_prompts.py` — correctly mirroring the new `src/scene/agent/prompts.py` under `test/` per convention — with well-formed/missing-file/malformed/missing-field cases, while requiring the full `pdm run pytest` suite (including the three existing test files touching the edited call sites) to pass before completion. No lore conflicts found; the encounter is reviewable and consistent with project standards as scripted.

### Completed - 2026-08-29T01:50:54Z - John Hoff

Implemented as planned: agent-prompts.yaml added at the project root (tracked, not gitignored) with the coordinator, continuity_editor, and rendering prompt text verified byte-for-byte identical to the original inline literals; src/scene/agent/prompts.py added with a PromptSet dataclass and load_prompts() loader mirroring registry.py's conventions; loop.py, continuity.py, and rendering.py now source their prompts via load_prompts() with public names preserved. Added test/scene/agent/test_prompts.py covering well-formed load, missing file, malformed top-level, missing section, missing field, and empty field. pdm run lint passes clean; pdm run pytest passes all 477 tests with prompts.py at 100% coverage.
