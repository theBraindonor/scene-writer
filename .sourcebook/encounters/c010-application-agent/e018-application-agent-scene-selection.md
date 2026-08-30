---
archived: false
campaign: c010-application-agent
created_by: John Hoff
created_on: '2026-08-30T22:16:44Z'
depends_on: []
kind: scripted
name: e018-application-agent-scene-selection
regions:
- agent
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-30T22:45:40Z'
---

## Requirements

Extend the application agent (`docs/application-agent.md`) with the Scenes tier: the
stateful select-then-act pattern where a scene must be selected or created before other
scene tools can act on it, matching the Scenes tab's own selection-driven manual UI.
`render_scene` (generating prose) is explicitly out of scope for this encounter and lands
in a follow-up — it requires bridging a synchronous tool call into the existing async
rendering pipeline, a distinct and riskier piece of engineering from plain CRUD.

- `ApplicationState` gains `current_scene_id: int | None = None`, and `ApplicationTab`
  gains `SCENES = "scenes"`.
- A new `scene.agent.application.tools.scene` module provides `build_scene_tools(state) ->
  list[Tool]`:
  - `list_scenes` — the open story's scenes, each flagged `is_selected` (per the flag
    already agreed for `docs/application-agent.md`), each including its assigned
    characters/locations (id + name) inline so the agent doesn't need extra calls to see a
    scene's cast.
  - `select_scene(scene_id)` — selects a scene belonging to the open story as current;
    switches the window to the Scenes tab and shows it.
  - `create_scene(brief, position=None, heading=None, required_actions=None,
    desired_outcome=None, target_length=None, pov_character_id=None)` — creates a scene in
    the open story and selects it as a side effect. `position` defaults to the end of the
    story when omitted, matching the manual "+" button.
  - `update_scene(position=None, heading=None, brief=None, required_actions=None,
    desired_outcome=None, target_length=None, pov_character_id=None)` — no `scene_id`
    parameter; acts on the selected scene.
  - `delete_scene()` — no parameters; deletes the selected scene and clears the selection.
  - `assign_character_to_scene(character_id)` / `unassign_character_from_scene(character_id)`
    and `assign_location_to_scene(location_id)` / `unassign_location_from_scene(location_id)`
    — no `scene_id` parameter; act on the selected scene's cast/location assignments.
- `src/scene/gui/main_window.py` wires `build_scene_tools` into the application agent's
  tool list, and its post-turn sync keeps the Scenes tab's on-screen selection permanently
  in sync with `ApplicationState.current_scene_id` — not just when the Scenes tab is the
  one the current turn touched (see Rationale: scene selection is persistent application
  state read by later turns, unlike the fire-and-forget Characters/Locations selection).
  Switching the open story (manually or via chat) clears `current_scene_id`.
- `agent-prompts.yaml`'s `application_agent.system_prompt` is extended to describe the
  select-then-act pattern for scenes and the cast/location assignment tools, while still
  stating that generating prose is not yet available.
- `docs/application-agent.md` is updated only if implementation reveals a real deviation
  from what it already says about Scenes (it already documents this tier's shape) — per
  this campaign's living-documentation requirement.

## Rationale

**Scene selection persists across turns; Character/Location selection doesn't.** In
`e017-application-agent-direct-entities`, `current_character_id`/`current_location_id` are
purely cosmetic: they drive which row gets re-selected in the UI immediately after a tool
call, but no tool logic ever reads them back to decide what to act on next. Scenes are
different by design (`docs/application-agent.md`'s "stateful entity" tier): `update_scene`,
`delete_scene`, and the assignment tools have no `scene_id` parameter at all — they act on
whatever `select_scene`/`create_scene` selected in a *previous* tool call, potentially in a
*previous* turn of the conversation. That makes `current_scene_id` real, load-bearing
application state, not a one-shot UI convenience. `MainWindow._on_chat_turn_completed`
already calls `entity_column.set_story(...)` on every turn when the story hasn't changed,
which unconditionally resets every sub-widget's selection (Scenes included) to none as a
side effect of reloading their lists — harmless for Characters/Locations, since nothing
reads their post-turn selection back, but it would silently desync the Scenes tab's
on-screen selection from `ApplicationState.current_scene_id` every time a turn touched a
different tab. The fix is a dedicated `EntityColumn.refresh_scene_selection(scene_id)` that
runs unconditionally after every turn (whenever a story is open), independent of
`EntityColumn.show_scenes_tab()` (which only switches which tab is visible) — so the
Scenes tab always reflects the agent's actual selection whenever the user looks at it,
regardless of what the most recent turn was about.

**Switching stories clears `current_scene_id`.** `EntityColumn.set_story()` already resets
the Scenes widget's selection to none on a story change (a scene from the old story can't
be meaningfully selected once a different story is open). `MainWindow._on_story_selected`
— which runs for both manual (`StoryHeader`) and chat-driven story switches — now also
clears `application_state.current_scene_id` there, once, on an actual change of story;
deliberately *not* inside `open_story`/`create_story`'s handlers, so that "opening" the
story that's already open doesn't spuriously drop an in-progress scene selection.

**`create_scene`'s `position` is optional here, unlike the coordinator's.** The
coordinator's `create_scene` requires `position` explicitly (a headless data API has no
sensible default). The application agent mirrors the manual "+" button instead: appending
to the end of the story is what a person clicking "new scene" gets, so that's the default
here too, with `position` still available for the agent to place it deliberately when
asked.

**Scene dicts inline their cast rather than adding `list_characters_for_scene`/
`list_locations_for_scene` tools.** The coordinator exposes those as separate tools because
it has no notion of "the scene currently being discussed." Here, every tool that returns or
touches a scene (`select_scene`, `create_scene`, `update_scene`, the assign/unassign tools)
already knows exactly which scene is relevant, so folding `characters`/`locations` (id +
name) directly into the scene dict answers "who/where is in this scene" without a second
round trip — consistent with `docs/application-agent.md`'s "the agent doesn't need to be
too aware of the underlying model" framing, just applied to scene *composition* rather than
scene *selection*.

**No confirmation dialog equivalent for `delete_scene`.** Matches the precedent already set
by `delete_character`/`delete_location` in `e017`: the person already gave explicit
instruction in chat, so the tool acts directly rather than emulating the manual UI's
`QMessageBox.question` confirmation.

**`select_scene` rejects a scene from a different story.** The application agent's mental
model has exactly one story on screen at a time; a scene from an unopened story would leave
the Scenes tab (scoped to the open story's list) unable to display it. `select_scene`
verifies `scene.story_id == state.current_story_id` and returns a clear error otherwise,
mirroring `open_story` as the *only* correct way to change which story's scenes the agent
can see.

## Plan

1. `src/scene/agent/application/state.py`:
   - Add `SCENES = "scenes"` to `ApplicationTab`.
   - Add `current_scene_id: int | None = None` to `ApplicationState`.

2. New `src/scene/agent/application/tools/scene.py` — `build_scene_tools(state:
   ApplicationState) -> list[Tool]`, using `scene.core.scene` (`create_scene`, `get_scene`,
   `list_scenes`, `update_scene`, `delete_scene`), `scene.core.scene_character`
   (`assign_character`, `unassign_character`, `list_characters_for_scene`), and
   `scene.core.scene_location` (`assign_location`, `unassign_location`,
   `list_locations_for_scene`):
   - `_scene_dict(session, scene, state)`: id, position, heading, brief, required_actions,
     pov_character_id, desired_outcome, target_length, `characters` (`[{"id", "name"}]` via
     `list_characters_for_scene`), `locations` (same shape via `list_locations_for_scene`),
     and `is_selected: scene.id == state.current_scene_id`.
   - `list_scenes_handler`: requires `state.current_story_id` (else the same "No story is
     open" error `e017` established); returns `{"scenes": [_scene_dict(...), ...]}` for
     `scene.core.scene.list_scenes(session, state.current_story_id)`.
   - `select_scene_handler(scene_id)`: requires an open story; `scene_id` is
     required (friendly error if missing, mirroring `open_story`'s `story_id` guard); loads
     via `get_scene`; not-found error if missing; if `scene.story_id != state.
     current_story_id`, return `{"error": f"Scene {scene_id} does not belong to the open
     story."}`; otherwise sets `state.current_scene_id = scene_id`, `state.current_tab =
     ApplicationTab.SCENES`, returns `_scene_dict(...)`.
   - `create_scene_handler(brief, position=None, heading=None, required_actions=None,
     desired_outcome=None, target_length=None, pov_character_id=None)`: requires an open
     story; `position` defaults to `len(list_scenes(session, state.current_story_id))` when
     omitted; calls `scene.core.scene.create_scene(...)` inside a `try/except ValueError`
     (invalid `pov_character_id`) returning `{"error": str(error)}`; on success sets
     `current_scene_id`/`current_tab` like `select_scene`.
   - `update_scene_handler(...)`: requires `state.current_scene_id` (else `{"error": "No
     scene is selected. Select one with select_scene, or create one with create_scene."}`);
     calls `scene.core.scene.update_scene(session, state.current_scene_id, ...)` in the same
     `try/except ValueError` pattern; sets `current_tab = ApplicationTab.SCENES`.
   - `delete_scene_handler()`: requires a selected scene (same error as above); calls
     `scene.core.scene.delete_scene`; sets `state.current_scene_id = None`, `current_tab =
     ApplicationTab.SCENES`; returns `{"deleted": True, "id": <the deleted id>}`.
   - `assign_character_to_scene_handler(character_id)` / `unassign_character_from_scene_
     handler(character_id)`: require a selected scene and a `character_id` argument
     (friendly errors for each, mirroring `e017`'s id-required guards); call
     `scene.core.scene_character.assign_character`/`unassign_character` in a
     `try/except ValueError` (cross-story mismatch) → `{"error": str(error)}`; on success
     set `current_tab = ApplicationTab.SCENES` and return the current scene's
     `_scene_dict(...)` so the agent sees the updated cast directly.
   - `assign_location_to_scene_handler(location_id)` / `unassign_location_from_scene_
     handler(location_id)`: same shape, using `scene.core.scene_location`.
   - Tool schemas: `position`/`heading`/`brief`/`required_actions`/`target_length`/
     `desired_outcome`/`pov_character_id` property descriptions carried over verbatim from
     the coordinator's `tools/scene.py`; only `brief` is `required` on `create_scene` (not
     `position`, per the Rationale above).

3. `src/scene/gui/entity_column/column.py`:
   - Add `refresh_scene_selection(self, select_scene_id: int | None) -> None`: `self.scenes.
     refresh(select_scene_id=select_scene_id)`.
   - Add `show_scenes_tab(self) -> None`: `self.tabs.setCurrentIndex(self._SCENES_TAB_INDEX)`.

4. `src/scene/gui/main_window.py`:
   - Import `build_scene_tools` from `scene.agent.application.tools.scene`; add
     `*build_scene_tools(self.application_state)` to `self.application_tools`.
   - `_on_story_selected`: add `self.application_state.current_scene_id = None` (clearing
     the agent's remembered scene selection whenever the open story actually changes).
   - `_sync_entity_column_tab`: before the existing tab-dispatch, unconditionally call
     `self.entity_column.refresh_scene_selection(self.application_state.current_scene_id)`
     whenever `self.current_story_id is not None` (independent of `current_tab`); add a
     branch `elif tab is ApplicationTab.SCENES: self.entity_column.show_scenes_tab()` to the
     existing dispatch (which now only needs to switch tabs, since selection is handled by
     the unconditional call above).

5. `agent-prompts.yaml`: extend `application_agent.system_prompt` with a paragraph covering
   scenes — that a scene must be selected or created before it can be updated, deleted, or
   have its cast/locations changed, that those operations always act on whichever scene is
   currently selected, and that generating a scene's prose is still not available.

6. Tests:
   - New `test/scene/agent/application/tools/test_scene.py`, mirroring
     `test/scene/agent/coordinator/tools/test_scene.py`'s coverage (create/update/delete,
     `pov_character_id` validation, not-found paths) but for the new shape: `is_selected`
     flag; no `story_id`/`scene_id` parameters on `update_scene`/`delete_scene`/the
     assign/unassign tools (asserted the same way `e017`'s
     `test_story_tools_have_no_story_id_parameter_except_open_story` does); `select_scene`
     rejecting a scene from a different story; `create_scene`'s default end-of-story
     `position`; the "no story is open" and "no scene is selected" error paths; assignment
     tools returning the updated scene's cast; and cross-story assignment producing a tool
     error (mirroring the coordinator's `test_assign_character_cross_story_returns_tool_
     error`).
   - `test/scene/gui/entity_column/test_column.py`: add direct tests for
     `refresh_scene_selection` and `show_scenes_tab` (closing the gap `e017`'s reviewer
     flagged for the equivalent Characters/Locations methods, this time addressed directly
     rather than left to indirect coverage).
   - `test/scene/gui/test_main_window.py`: add a chat-driven test creating a scene via chat
     and asserting the Scenes tab becomes current with it selected; a test asserting that
     asking the agent to update the *previously selected* scene in a *second, separate* chat
     turn (after an intervening turn that touched a different tab) still acts on the correct
     scene and that scene remains selected in the Scenes tab even though the intervening
     turn's tab is the one currently visible — the specific regression this encounter's
     Rationale exists to prevent; and a test confirming that opening a different story via
     chat clears any previously selected scene (`window.application_state.current_scene_id
     is None`).

## Verification

- `pdm run pytest` — full suite passes, including the new `test/scene/agent/application/
  tools/test_scene.py` and the updated `test_column.py`/`test_main_window.py`, with the
  auto-generated `htmlcov/index.html` coverage report covering the new/changed code.
- `pdm run lint` — clean (ruff, 120-char line length).
- Manual smoke check via the `run` skill (or an equivalent driver script, as used for
  `e017`): create a scene via chat and confirm the Scenes tab shows it selected; in a
  separate follow-up message, update a character (confirming the Characters tab takes
  over); then, in a third message with no scene id mentioned, ask the agent to update the
  scene's brief and confirm it correctly acts on the scene selected two turns earlier, with
  the Scenes tab now showing that update; assign a character and a location to the scene
  via chat and confirm both show up in the manual UI's "Characters/Locations in Scene"
  checklists.

## Log

### Review - 2026-08-30T22:19:26Z - John Hoff

Reviewed e018-application-agent-scene-selection against the two applicable world lore items (linting, unit-testing); both are explicitly and correctly honored in the Verification section (ruff at 120 chars; full `pdm run pytest` with HTML coverage, new/updated test files correctly mirroring their `src/` module paths). Spot-checked the Plan's technical claims against the current `agent`/`gui` region code (`state.py`, `column.py`, `scenes.py`, `main_window.py`, `docs/application-agent.md`, and the referenced `scene.core` functions) and found it well-grounded — the described insertion points, signatures, and existing behaviors (e.g. `EntityColumn.set_story()` already resetting scene selection, `_on_story_selected` only firing on actual story changes) match reality rather than being speculative. No lore conflicts and no gaps found within the bounded reading surface; approved.

### Message - 2026-08-30T22:41:33Z - John Hoff

Deviation found during implementation, via the live manual smoke test (real MainWindow, real LLM): `assign_character_to_scene`/`assign_location_to_scene`, as planned, called `scene.core.scene_character.assign_character`/`scene.core.scene_location.assign_location` inside only a `try/except ValueError`. Both functions raise a raw `sqlalchemy.exc.IntegrityError` (unique constraint on `(scene_id, character_id)`/`(scene_id, location_id)`) when the character/location is already assigned to the scene, which that guard didn't catch. Uncaught, this exception propagates out of the tool handler and crashes `ChatPanel._TurnWorker`'s background thread silently mid-turn (it has no broad exception handling, unlike `RenderingColumn`'s `_RenderWorker`) — `turn_completed` never fires, and the chat input stays disabled indefinitely with no visible error. This was reproduced live: the agent proactively assigned a mentioned character while creating a scene, then a later turn asking it to "assign X to it" again hung the UI. Fixed by making both assign handlers idempotent — each now checks the scene's current cast/locations first and only calls `assign_character`/`assign_location` if not already present, so re-assigning an already-assigned character or location is a no-op success rather than a crash. Added `test_assign_character_to_scene_is_idempotent_when_already_assigned` and `test_assign_location_to_scene_is_idempotent_when_already_assigned` to `test/scene/agent/application/tools/test_scene.py`. Re-ran the smoke test end-to-end afterward and confirmed all steps pass. Note for a possible future encounter: `ChatPanel`/`_TurnWorker` having no broad exception handling around `run_turn(...)` is a pre-existing gap (predates this campaign, likely also affects the CLI coordinator's equivalent path) that lets any single unexpected tool/network exception hang the chat UI silently with no error surfaced — out of scope to fix here, but worth its own encounter.

### Completed - 2026-08-30T22:45:40Z - John Hoff

Verification passed: pdm run pytest (710 tests, including new test/scene/agent/application/tools/test_scene.py and updated test_column.py/test_main_window.py), 97% overall coverage with all new/changed files at 100%. pdm run lint clean. Live manual smoke test via a driver script (real MainWindow, real temp DB, real configured OpenRouter model) confirmed: creating a scene via chat selects it and switches to Scenes; an intervening turn touching Characters leaves the scene selection intact in both ApplicationState and the (hidden) Scenes widget; a later message with no scene id mentioned correctly updates that same scene and re-shows it selected; and character/location assignment via chat both persisted correctly. One bug found and fixed during the smoke test: assign_character_to_scene/assign_location_to_scene crashed the chat's background thread on a duplicate assignment (uncaught IntegrityError) -- fixed by making both idempotent, with tests added and the smoke test re-run clean afterward.
