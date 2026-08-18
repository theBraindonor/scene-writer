---
archived: false
campaign: c003-coordinating-agent
created_by: John Hoff
created_on: '2026-08-18T15:03:10Z'
depends_on:
- e004-story-tools
kind: scripted
name: e005-coordinator-cli-state-display
regions:
- agent
- cli
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T18:22:29Z'
---

# E005 — Coordinator TUI

## Requirements
- Add `textual` as a runtime dependency, and `pytest-asyncio` as a dev dependency for headlessly testing the TUI; configure pytest for async tests (e.g. `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`).
- Add a `CoordinatorState` to `scene.agent.coordinator` holding mutable session state: `history: list[dict[str, Any]]` and `current_story_id: int | None` (starts `None`). This replaces the fixed `default_story_id` concept `e004-story-tools` introduced.
- Update `scene.agent.coordinator.tools.story.build_story_tools` to accept a `CoordinatorState` instead of a fixed `default_story_id`. Single-story tools (`get_story`, `update_story`, `archive_story`, `unarchive_story`) resolve their target story id as: the model's explicit `story_id` argument if given, else `state.current_story_id`; if neither is available, return a clear tool-result error telling the model to create or select a story first (not raise). Whenever a tool successfully resolves and operates on a story id (explicit or defaulted), it updates `state.current_story_id` to that id, so a story the model just created, fetched, or switched to becomes "current" for subsequent calls without the model needing to repeat the id. `create_story` sets `state.current_story_id` to the newly created story's id. `list_stories` does not change `state.current_story_id`.
- Replace `scene-coordinator chat`'s plain-text REPL with a Textual TUI: two vertical columns — a left-hand chat pane (scrollable transcript plus a text input) and a right-hand pane that renders the current story's fields (title, scenario, style guidance, archived status), re-rendered fresh from `scene.core.story.get_story` after every turn. The right-hand pane shows a clear placeholder when `state.current_story_id` is `None`.
- `chat` takes no story id argument. It still resolves the coordinating agent's LLM config once via `get_llm_config(AgentRole.COORDINATING)` before launching the TUI, surfacing a resolution failure as a clear CLI error exactly as today (`e003-coordinator-cli`), rather than opening the TUI at all.
- The input box recognizes `/quit` (exits the app) and `/clear` (resets both `state.history` and `state.current_story_id` to a blank session, clearing the chat transcript and returning the right-hand pane to its placeholder). Any other `/`-prefixed input is shown as an inline notice in the chat pane rather than sent to the model.
- The blocking `run_turn`/LLM call runs off the UI's event loop (e.g. a Textual worker thread) so the TUI stays responsive while waiting on a response.
- `test/scene/cli/test_coordinator.py` (e003's `CliRunner`-based tests) is built entirely around the old `chat(story_id)` stdin-REPL signature and will not survive this rescope as-is. Retire it in favor of Textual-native coverage: fold every scenario it currently proves — config-resolution failure surfaced as a clear error, a plain chat turn, and a tool-call round trip that persists — into the new Textual test file, using `CoordinatorState`/story-lookup behavior instead of a required `story_id` argument. Do not leave both files asserting against incompatible signatures.
- Cover the `CoordinatorState`-aware story tools with updated/expanded unit tests (current-story defaulting, switching between stories, and the "no current story" error path). Cover the TUI's `/quit`, `/clear`, a plain chat turn, a scripted tool-call round trip (creating a story and confirming the right-hand pane reflects it), and a config-resolution failure, using Textual's headless `App.run_test()`, mocking `scene.agent.llm.complete` and `scene.agent.config.get_llm_config` so no real network call is made.

## Rationale
Originally scoped as inline REPL text output, this encounter was rescoped in place (while still
`draft`) at the developer's direction: once story tools existed and the agent could list/create
stories itself via tool calls, requiring a story id up front on the command line stopped pulling
its weight, and a plain-text REPL was judged too limited a foundation for the richer interaction
(clean live state display, more commands) planned as more tools are added. A two-pane Textual TUI
replaces it — the left pane for conversation, the right pane doing what this encounter always
intended: showing the current data objects' state immediately after the LLM updates them, now via
a dedicated pane refreshed from `scene.core` rather than printed inline. Moving the "current
story" concept from a fixed CLI argument to mutable session state set by the tools themselves is
a necessary consequence: `e004-story-tools`'s tools took a fixed `default_story_id` captured once
at `chat` startup, which no longer exists once `chat` takes no story id. `e004`'s encounter body
is completed and locked, so this change to its shipped code is recorded here rather than by
reopening it. An independent review of this rescoped draft additionally flagged that
`test/scene/cli/test_coordinator.py` — e003's `CliRunner`-based coverage of the old `chat(story_id)`
signature — was otherwise left unaddressed and would break under this rescope; its retirement in
favor of Textual-native tests is folded into the Requirements/Plan below, and this encounter is
now also assigned to the `agent` region (previously `cli` only) since its Plan touches
`scene/agent/coordinator/` files.

## Plan
1. Add `textual` to `[project] dependencies`; add `pytest-asyncio` to the `dev` optional-dependency group and set `asyncio_mode = "auto"` under `[tool.pytest.ini_options]` in `pyproject.toml`; update `pdm.lock` via `pdm install -G dev`.
2. Add `scene/agent/coordinator/state.py` defining `CoordinatorState` (`history: list[dict[str, Any]]`, `current_story_id: int | None`).
3. Update `scene/agent/coordinator/tools/story.py`'s `build_story_tools(state: CoordinatorState)` to implement the story-id resolution/update rules in Requirements, via a small shared helper used by the four single-story handlers.
4. Add a Textual app module (e.g. `scene/cli/coordinator_app.py`) with a `CoordinatorApp` composing the two-column layout, wiring input submission to slash-command handling or `run_turn` (via a worker thread), and refreshing the right-hand pane from `scene.core.story.get_story` after each turn and after `/clear`.
5. Update `scene/cli/coordinator.py`'s `chat` command to drop the `story_id` parameter, keep the existing LLM-config-resolution try/except, and launch `CoordinatorApp(config).run()` on success.
6. Update `test/scene/agent/coordinator/tools/test_story.py` for the new `CoordinatorState`-based defaulting/switching/no-current-story behavior.
7. Delete `test/scene/cli/test_coordinator.py` and add `test/scene/cli/test_coordinator_app.py` using Textual's `App.run_test()`, covering every scenario the deleted file proved (config-resolution failure, a plain chat turn, a persisting tool-call round trip) plus `/quit`, `/clear`, and the right-hand pane's refresh, mocking `scene.agent.llm.complete` and `scene.agent.config.get_llm_config`.
8. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green — including confirming `test/scene/cli/test_coordinator.py` no longer exists and every scenario it used to cover is proven by `test_coordinator_app.py` instead.
- `pdm run lint` reports zero errors.
- Manually run `pdm run scene-coordinator chat` (no story id) against a running LM Studio server: confirm the TUI opens with an empty right-hand pane, ask the agent to create a new story and confirm the right-hand pane immediately shows it, ask it to update the scenario and confirm the pane updates, then confirm `/clear` blanks both panes and `/quit` exits cleanly.

## Log

### Review - 2026-08-18T18:05:14Z - John Hoff

Reviewed e005-coordinator-cli-state-display's current body against the two applicable world-assigned lore items (linting, unit-testing; neither region carries additional lore) and against e001-e004's real shipped interfaces. Both previously-flagged gaps are now substantively resolved: `regions` correctly includes `agent` alongside `cli` (justified by the Plan's real file targets), and the Plan now explicitly retires `test/scene/cli/test_coordinator.py` — confirmed by reading it that it is indeed built entirely around the old `chat(story_id)` signature — in favor of a new `test/scene/cli/test_coordinator_app.py`. One residual gap: the "fold every scenario" claim names only 3 of the deleted file's 6 actual test scenarios (the other 3 are either legitimately obsolete or covered under a different name, so this is a documentation imprecision rather than lost coverage), and more importantly the config-resolution-failure scenario — which lives entirely in `coordinator.py`'s own `chat()` logic, prior to `CoordinatorApp` ever being instantiated — is folded into `test_coordinator_app.py` "using Textual's `App.run_test()`," which doesn't structurally fit that code path and leaves the still-modified `src/scene/cli/coordinator.py` without a test file mirroring it per the unit-testing lore's own naming convention. This is a note for the implementer, not a lore conflict rising to rejection — the rest of the Plan (CoordinatorState replacing `default_story_id`, the four single-story handlers' resolution rules, `pdm run lint`/`pdm run pytest` gating) is accurate and consistent with the real source. PASS-WITH-NOTES.

### Completed - 2026-08-18T18:22:29Z - John Hoff

Verified: pdm run pytest passes 176/176 with 100% coverage, including 9 new Textual App.run_test() tests in test/scene/cli/test_coordinator_app.py covering /quit, /clear (resets history, current story, chat log, and story pane), a plain chat turn, a scripted tool-call round trip that creates a story and updates the right-hand pane, blank-input handling, and the defensive missing-story-in-pane branch. test/scene/agent/coordinator/tools/test_story.py rewritten for CoordinatorState-based defaulting/switching/no-current-story-error behavior across all four single-story tools. test/scene/cli/test_coordinator.py rewritten (old story_id-based stdin-REPL tests deleted) to mirror the now-much-smaller coordinator.py: config-resolution failure and CoordinatorApp wiring, per the second review's note that this scenario belongs in a file mirroring coordinator.py rather than squeezed into the Textual app harness. pdm run lint reports zero errors. textual and pytest-asyncio added as dependencies; asyncio_mode = "auto" configured.

Manually verified the real production stack (get_llm_config -> CoordinatorState -> build_story_tools -> run_turn) end-to-end against the live LM Studio server outside the TUI rendering layer: asked it to create a story, confirmed a real tool call created it, state.current_story_id was correctly set, and the story persisted (confirmed via scene-data story get). Could not personally drive the actual rendered TUI from this sandboxed shell, since Textual takes over the terminal (alternate screen/raw mode) and won't render through piped stdin/stdout; asked the developer to manually run `pdm run scene-coordinator chat` in a real terminal to visually confirm the two-column layout, live pane refresh, /clear, and /quit.

Implementation delivered: src/scene/agent/coordinator/state.py (CoordinatorState), src/scene/agent/coordinator/tools/story.py rewritten to take CoordinatorState instead of e004's fixed default_story_id (a locked encounter's shipped code, changed here per this encounter's Rationale), src/scene/cli/coordinator_app.py (new Textual CoordinatorApp with the two-column layout, worker-threaded LLM calls, and testable chat_lines/_render_story_pane surfaces), and src/scene/cli/coordinator.py's chat command simplified to config resolution plus launching the TUI.
