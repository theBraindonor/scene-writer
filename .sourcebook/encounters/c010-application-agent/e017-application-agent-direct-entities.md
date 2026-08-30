---
archived: false
campaign: c010-application-agent
created_by: John Hoff
created_on: '2026-08-30T20:50:50Z'
depends_on: []
kind: scripted
name: e017-application-agent-direct-entities
regions:
- agent
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-30T22:07:45Z'
---

## Requirements

Introduce the application agent (`docs/application-agent.md`) and wire it into the GUI in place
of the coordinator, covering the "direct entity" tier only: Story, Characters, and Locations.
Scenes (selection state, `select_scene`/`create_scene`, and `render_scene`) are explicitly out of
scope for this encounter and land in a follow-up.

- A new `AgentRole.APPLICATION` (`SCENE_APPLICATION_AGENT` env var) selects this agent's model
  independently of the coordinator/rendering/continuity roles, following the existing pattern in
  `src/scene/agent/role.py` and `src/scene/agent/config.py`.
- A new `application_agent.system_prompt` section in `agent-prompts.yaml`, loaded via a new
  `application_agent_system_prompt` field on `PromptSet` (`src/scene/agent/prompts.py`), describing
  only the capabilities this encounter implements (Story/Characters/Locations) — it must not
  reference scene selection or rendering, which don't exist yet.
- A new `scene.agent.application` package providing:
  - `ApplicationState` (`current_story_id`, `current_tab`, `current_character_id`,
    `current_location_id`) and an `ApplicationTab` enum (`STORY`, `CHARACTERS`, `LOCATIONS`) —
    `SCENES` is not added yet.
  - Tool builders `build_story_tools`, `build_character_tools`, `build_location_tools`,
    implementing exactly the Story and Character/Location tool catalogs in
    `docs/application-agent.md`: `list_stories` (with the `is_open` flag per story already agreed
    for this document), `open_story`, `create_story`, `update_story`, `archive_story`,
    `unarchive_story`, `list_characters`, `create_character`, `update_character`,
    `delete_character`, `list_locations`, `create_location`, `update_location`,
    `delete_location`.
- `src/scene/gui/main_window.py`'s chat panel is now built from `ApplicationState` and these three
  tool builders (not `CoordinatorState`/the coordinator's tool builders), resolved against
  `AgentRole.APPLICATION`. After every chat turn, in addition to the existing story-sync behavior,
  the entity column's visible tab (and, for Characters/Locations, the selected row) is updated to
  match `ApplicationState.current_tab`/`current_character_id`/`current_location_id` — exactly as if
  the person had clicked there themselves.
- The CLI's coordinator (`scene-coordinator chat`) is untouched and keeps behaving exactly as
  before — this encounter only changes what the GUI's chat panel is wired to.
- `docs/application-agent.md` is corrected in one place found while implementing it: the
  `generation_guidance` tool parameter name is confirmed (not renamed to match the underlying
  `generation_guideance` model typo — see Rationale) and the Story tools' description gains a note
  that Character/Location/Scene tools always act on the open story, with no `story_id` override
  (a simplification from the coordinator's tools that the document didn't previously call out
  explicitly).

## Rationale

**Only Story/Characters/Locations this time.** These three tabs share one shape — a simple,
stateless "resolve by id/name, act, done" tool per `docs/application-agent.md`'s "direct entities"
tier — while Scenes need selection state that persists across tool calls and a synchronous render
step tied into the existing async `RenderingColumn` worker. Bundling both tiers into one encounter
would make it large and would put the more novel, riskier part (scene selection lifecycle +
render integration) behind the same review/verification gate as the straightforward part. Splitting
lets the direct-entity tier ship and get real use while the scene tier is designed and reviewed on
its own.

**No `story_id` parameter on Character/Location tools.** The coordinator's equivalent tools accept
an optional `story_id` override because the coordinator is a headless data API with no notion of
"the story currently on screen." The application agent has exactly one story on screen at a time
by construction (`docs/application-agent.md`'s mental model) — there is no such thing as "a
character in some other story" from its point of view, since acting on a different story first
requires `open_story`. Dropping the parameter isn't a missing feature; it's the direct consequence
of the agent's perspective, and keeping it would let the model reference a story it can't actually
see. Story tools still don't take a `story_id` on `update_story`/`archive_story`/`unarchive_story`
for the same reason; only `open_story` (which is *how* the open story changes) and `list_stories`
(which is how any other story becomes visible before it's opened) reference a story by id.

**Tool-facing `generation_guidance` vs. the model's `generation_guideance`.** `scene.core.story`'s
functions and the coordinator's existing tool both spell this field `generation_guideance` (a
long-standing typo baked into the schema). `docs/application-agent.md` already committed to the
correctly-spelled `generation_guidance` as the tool-facing name. Rather than propagate the typo to
a brand-new tool surface, the application agent's `create_story`/`update_story` handlers accept
`generation_guidance` and translate it to the `generation_guideance=` keyword when calling
`scene.core.story`. This is a one-line translation at the handler boundary, not a schema change.

**Selection sync mirrors, rather than optimizes, the existing post-turn refresh.**
`MainWindow._on_chat_turn_completed` already unconditionally calls `entity_column.set_story(...)`
after every chat turn regardless of which single field actually changed (see
`test_chat_creating_character_refreshes_entity_column`, which already relies on this). This
encounter adds one more full `refresh(select_*_id=...)` call on top of that, targeted at whichever
tab `ApplicationState.current_tab` names, so the just-touched record is also *selected* (its detail
form populated), not just present in the list. This costs an extra query per touched tab per turn,
which is consistent with the codebase's existing preference for a simple, fully-reloaded refresh
over incremental UI patching (see `EntityColumn.set_story`, `FullStoryRenderController`'s
scene-by-scene commits) — not something this encounter should deviate from just for this feature.

**`EntityColumn` gains plain tab-switch helper methods, not an `ApplicationTab` dependency.**
`show_story_tab()`, `show_characters_tab(select_character_id=None)`, and
`show_locations_tab(select_location_id=None)` are added to `EntityColumn` itself (indexing its own
`QTabWidget` by the constants it already defines internally), keeping `scene.gui.entity_column` free
of any dependency on `scene.agent.application`'s enum. `MainWindow` — which already imports both
layers — does the `ApplicationTab` → method mapping. This mirrors the existing direction of
dependency (`gui` depends on `agent`, never the reverse).

**System prompt scoped to what actually exists.** Writing the full application-agent persona
(including scene selection and rendering) into `agent-prompts.yaml` now, before those tools exist,
would hand the model tool names it can't call. The prompt added here only describes Story/
Characters/Locations; the scene-tools encounter extends it.

**Chat transcript heading renamed from "Coordinator" to "Assistant."** `ChatPanel`'s transcript
widget (`src/scene/gui/chat_panel.py`) labels each agent turn "Coordinator," naming the agent this
campaign is replacing. Since `ChatPanel` itself stays agent-agnostic (it already takes `state` and
`tools` as opaque parameters), it also gains a `system_prompt` constructor parameter instead of
importing the coordinator's `DEFAULT_SYSTEM_PROMPT` directly — the caller (`MainWindow`) now always
supplies the prompt for whichever agent it's wiring up.

## Plan

1. `src/scene/agent/role.py`: add `APPLICATION = "SCENE_APPLICATION_AGENT"` to `AgentRole`,
   alongside the existing `COORDINATING`/`RENDERING`/`CONTINUITY_EDITING` members.

2. `.env.example`: add a `SCENE_APPLICATION_AGENT=` entry (with a comment matching the existing
   entries' style) directly after `SCENE_COORDINATING_AGENT`, describing it as the GUI's
   application-agent model selector.

3. `agent-prompts.yaml`:
   - Extend the header comment's section list with an `application_agent` entry.
   - Add a top-level `application_agent:` section with a `system_prompt:` describing: who the
     agent is (the Scene Writer application agent, operating the GUI directly rather than editing
     records blind); that it can open/create/update/archive the open story; that it can create,
     update, and delete characters and locations in the open story; that every tool call also
     changes what's visible on screen, so it should narrate actions in terms of what the user will
     see (e.g. "I've opened the Characters tab and updated Mara's motive"); and that it has no
     scene or rendering tools yet.

4. `src/scene/agent/prompts.py`: add `application_agent_system_prompt: str` to `PromptSet`, and in
   `load_prompts`, read the new `application_agent` section the same way `coordinator` is read
   today.

5. New package `src/scene/agent/application/`:
   - `__init__.py` (empty, matching `coordinator/__init__.py`).
   - `state.py`:
     ```python
     class ApplicationTab(Enum):
         STORY = "story"
         CHARACTERS = "characters"
         LOCATIONS = "locations"

     @dataclass
     class ApplicationState:
         history: list[dict[str, Any]] = field(default_factory=list)
         current_story_id: int | None = None
         current_tab: ApplicationTab | None = None
         current_character_id: int | None = None
         current_location_id: int | None = None
     ```
   - `tools/__init__.py` (empty).
   - `tools/story.py` — `build_story_tools(state: ApplicationState) -> list[Tool]` (`Tool` imported
     from `scene.agent.coordinator.loop`, the existing generic tool-calling engine, unchanged):
     - `list_stories(query=None, include_archived=False)`: lists stories via
       `scene.core.story.list_stories`, case-insensitively substring-filtered by `query` on title
       when given, each result including `is_open: story.id == state.current_story_id`.
     - `open_story(story_id)`: loads the story via `get_story`; not-found error if missing;
       otherwise sets `state.current_story_id = story_id`, `state.current_tab =
       ApplicationTab.STORY`, and returns the story.
     - `create_story(title, story_brief, style_guidance=None, generation_guidance=None)`: creates
       via `scene.core.story.create_story` (passing `generation_guideance=generation_guidance`),
       sets `current_story_id`/`current_tab` the same as `open_story`.
     - `update_story(title=None, story_brief=None, style_guidance=None, generation_guidance=None)`:
       requires `state.current_story_id` (a "no story is open — call open_story or create_story
       first" error otherwise); updates via `scene.core.story.update_story`; sets `current_tab =
       ApplicationTab.STORY`.
     - `archive_story()` / `unarchive_story()`: same current-story requirement; call
       `scene.core.story.archive_story`/`unarchive_story`; set `current_tab = STORY`.
   - `tools/character.py` — `build_character_tools(state) -> list[Tool]`:
     - `list_characters()`: requires an open story (empty-list-with-error semantics matching the
       coordinator's `_NO_CURRENT_STORY` pattern); lists `scene.core.character.list_characters` for
       `state.current_story_id`.
     - `create_character(name, description=None, motive=None)`: requires an open story; creates via
       `scene.core.character.create_character`; sets `state.current_character_id` to the new id and
       `state.current_tab = ApplicationTab.CHARACTERS`.
     - `update_character(character_id, name=None, description=None, motive=None)`: updates via
       `scene.core.character.update_character`; not-found error if missing; sets
       `current_character_id = character_id`, `current_tab = CHARACTERS`.
     - `delete_character(character_id)`: deletes via `scene.core.character.delete_character`;
       not-found error if missing; sets `current_character_id = None`, `current_tab = CHARACTERS`.
   - `tools/location.py` — `build_location_tools(state) -> list[Tool]`: `list_locations`,
     `create_location(name, description=None)`, `update_location(location_id, name=None,
     description=None)`, `delete_location(location_id)`, mirroring the character tools exactly
     (no `motive` field), setting `current_location_id`/`current_tab = ApplicationTab.LOCATIONS`.

6. `src/scene/gui/entity_column/column.py`: add `show_story_tab()`, `show_characters_tab
   (select_character_id: int | None = None)`, and `show_locations_tab(select_location_id: int |
   None = None)` methods to `EntityColumn`, switching `self.tabs.currentIndex()` to the
   corresponding tab and, for Characters/Locations, also calling
   `self.characters.refresh(select_character_id=...)` / `self.locations.refresh
   (select_location_id=...)`. No dependency on `scene.agent.application` is introduced here.

7. `src/scene/gui/chat_panel.py`:
   - Add a required `system_prompt: str` constructor parameter to `ChatPanel`, stored as
     `self._system_prompt`.
   - Thread it through to `_TurnWorker` (new constructor parameter, stored the same way) and use it
     in place of the hardcoded `DEFAULT_SYSTEM_PROMPT` in `_TurnWorker.run()`'s `run_turn(...)`
     call. Remove the now-unused `DEFAULT_SYSTEM_PROMPT` import.
   - Rename the transcript heading in `_AgentTurnWidget` from `"Coordinator"` to `"Assistant"`.

8. `src/scene/gui/main_window.py`:
   - Replace the `CoordinatorState`/coordinator tool-builder imports and `AgentRole.COORDINATING`
     lookup with `ApplicationState`/`ApplicationTab` and `build_story_tools`/`build_character_tools`
     /`build_location_tools` from `scene.agent.application`, resolved against
     `AgentRole.APPLICATION`. Update the error string to "Could not resolve the application agent's
     model: {error}".
   - Rename `self.coordinator_state`/`self.coordinator_tools` to `self.application_state`/
     `self.application_tools`.
   - Pass `system_prompt=load_prompts().application_agent_system_prompt` to the new `ChatPanel(...)`
     call.
   - Extend `_on_chat_turn_completed` to, after its existing story-sync branch, call a new
     `_sync_entity_column_tab()` that maps `self.application_state.current_tab` to
     `entity_column.show_story_tab()` / `show_characters_tab(current_character_id)` /
     `show_locations_tab(current_location_id)` (a `None` tab is a no-op).

9. Tests:
   - `test/scene/agent/test_role.py`: cover `AgentRole.APPLICATION.env_var ==
     "SCENE_APPLICATION_AGENT"`.
   - `test/scene/agent/test_prompts.py`: cover `load_prompts()` returning a non-empty
     `application_agent_system_prompt`, and the existing malformed-yaml coverage extended to the
     new section (missing `application_agent` section/`system_prompt` key raises the same way the
     existing sections do).
   - New `test/scene/agent/application/tools/test_story.py`, `test_character.py`,
     `test_location.py`, mirroring the coordinator's equivalent test files
     (`test/scene/agent/coordinator/tools/test_*.py`) but covering: `is_open`/no-`story_id`-param
     behavior for story tools; the "no story is open" error path for character/location tools when
     `state.current_story_id` is `None`; `current_tab`/`current_character_id`/`current_location_id`
     being set correctly by every tool; and the `generation_guidance` ↔ `generation_guideance`
     translation round-tripping through `create_story`/`update_story`.
   - `test/scene/gui/test_chat_panel.py`: update `make_panel`/`make_config` to pass a
     `system_prompt` argument to `ChatPanel(...)`; add a test asserting the given `system_prompt`
     is what's sent as the first (`role: system`) message to the stream, replacing reliance on the
     removed `DEFAULT_SYSTEM_PROMPT` import.
   - `test/scene/gui/test_main_window.py`:
     - Rename `test_selecting_story_sets_coordinator_state` to
       `test_selecting_story_sets_application_state`, updating the attribute it asserts on.
     - Update `test_chat_creating_story_updates_header_and_entity_column` and
       `test_chat_creating_character_refreshes_entity_column` for the renamed
       `application_state`/`application_tools` attributes.
     - Extend `test_chat_creating_character_refreshes_entity_column` to also assert
       `entity_column.tabs.currentIndex()` is the Characters tab and the new character ends up
       selected (`entity_column.characters.current_character_id` matches the created id).
     - Add `test_chat_updating_location_switches_to_locations_tab` (or similar): start on a
       different tab (e.g. Story), drive an `update_location` tool call through chat, assert the
       Locations tab becomes current and the edited location is selected.
     - Remove `test_chat_editing_scene_refreshes_entity_column` — `update_scene` is not one of this
       encounter's tools; an equivalent test is reintroduced by the scene-tools follow-up
       encounter once `select_scene`/`update_scene` exist on the application agent.
     - Update any test asserting the coordinator-specific error string
       ("Could not resolve the coordinating agent's model...") that covers `MainWindow`'s chat
       panel error path, to the new application-agent wording.

10. `docs/application-agent.md`: add a short note under the Story tools' intro (or the Interaction
    pattern section) stating explicitly that Character/Location/Scene tools always act on the open
    story, with no `story_id` parameter — codifying the Rationale above as part of the document
    itself, per this campaign's living-documentation requirement.

## Verification

- `pdm run pytest` — full suite passes, including the new `test/scene/agent/application/` tests
  and the updated `test/scene/gui/test_chat_panel.py`/`test_main_window.py`, with the
  auto-generated `htmlcov/index.html` coverage report covering the new package.
- `pdm run lint` — clean (ruff, 120-char line length).
- Manual smoke check via the `run` skill: launch the GUI, open a story via chat ("open the story
  called ..."), confirm the Story tab becomes active; ask it to create a character and confirm the
  Characters tab becomes active with the new character selected and its fields populated; switch
  manually to a different tab, then ask the agent to update a location, and confirm it switches to
  Locations and selects the edited location; confirm `scene-coordinator chat` (CLI) still works
  unaffected.

## Log

### Review - 2026-08-30T20:55:15Z - John Hoff

Reviewed against the two applicable lore items (linting, unit-testing), both purely process-level. The Plan explicitly satisfies both: Verification requires a clean `pdm run lint` and a fully-passing `pdm run pytest` run with its auto-generated coverage report, and step 9 lays out new/updated test files that correctly mirror the new `src/scene/agent/application/` package and the modified GUI/agent modules. No conflicts found. Minor, non-blocking observation: the new `EntityColumn` tab-switching methods and the `ApplicationState`/`ApplicationTab` dataclass aren't named as targets of a dedicated unit-test file, relying instead on indirect coverage through the chat-driven `test_main_window.py` and tool-builder tests — likely sufficient to satisfy the coverage requirement mechanically, but worth a second look during implementation. PASS-WITH-NOTES.

### Completed - 2026-08-30T22:07:45Z - John Hoff

Verification passed: pdm run pytest (664 tests, including new test/scene/agent/application/ tests and updated test/scene/gui/test_chat_panel.py and test_main_window.py), 97% overall coverage with the new scene.agent.application package at 100%. pdm run lint clean. Live manual smoke test via a driver script (real MainWindow, real temp DB, real configured OpenRouter model, no mocking) confirmed all three flows: opening a story by name switched to the Story tab; creating a character switched to Characters with it selected and its fields populated; a manual tab switch followed by a chat-driven location rename correctly switched to Locations and selected/populated the edited location. scene-coordinator CLI confirmed unaffected.
