# Application agent

## Purpose

The GUI currently drives the same coordinating agent as the CLI (`scene-coordinator chat`):
a data-oriented agent whose tools are thin wrappers over `scene.core`, addressed by
`story_id`/`scene_id`/etc. It has no notion of the GUI at all — it edits records, and the
window happens to refresh itself afterward.

The application agent replaces that agent inside the GUI. It is a conversational operator
of the application itself, not just of the database underneath it. Where the coordinator
asks "which row do I update," the application agent asks "what would I click." Every tool
it calls is something a person could also do by hand — open a story, switch to a tab,
select a scene, press Render — and its tool results describe what is now on screen, not
just what changed in storage.

This document describes the agent from its own point of view: what it believes the
application looks like, the rules that govern how it acts on it, and the full catalog of
tools it needs. It does not address how any of this is wired into the GUI's widgets,
threads, or signals — that is an implementation concern for later.

## Relationship to other agents

- **Coordinator** (CLI only, going forward): unchanged. A purely data-facing agent that
  edits stories/scenes/characters/locations by id, with no concept of an on-screen state.
- **Rendering agent**: unchanged. The application agent does not draft prose itself — its
  `render_scene` tool hands off to the existing rendering pipeline and reports back the
  result, the same way pressing the Render button does.
- **Continuity-editing agent**: unchanged, and invisible to the application agent beyond
  the fact that a render's follow-on continuity update happens as part of `render_scene`
  completing.

## The agent's mental model

The application agent believes it is looking at the same window a person sees, and that
the window always has exactly one **focus**:

- An **open story** — nothing else is possible until one is open. Opening a story is
  always the first move in a fresh conversation.
- Within that story, one **active tab** — Story, Characters, Locations, or Scenes — showing
  whichever record the agent last touched.
- Within the Scenes tab specifically, one **selected scene**, which is what an in-progress
  edit or a render applies to. No other tab has a persistent selection the agent needs to
  track: Story has only the one open story, and Characters/Locations are addressed
  directly by name each time without the agent needing to remember what's selected.

Every tool call both performs its action and leaves the window showing the result — an
`open_story` call doesn't just make a story "current," it switches the visible tab to
Story and populates it; an `update_character` call flips to Characters and shows the
character just edited. The agent should narrate its actions in those terms ("I've opened
*Ashwood Keep* and switched to the Characters tab...") because that is what the person
watching the screen will actually see happen.

## Interaction pattern

Two different patterns cover the four tabs, and the agent needs to know which applies to
what it's doing:

### Direct entities: Story, Characters, Locations

These tools are self-contained. Each one names its target (the open story implicitly, or
a character/location by id resolved from a prior `list_*` call) and does its work in one
call: find it, switch to its tab, show it, apply the change. There is no separate
"select a character" step exposed to the agent — asking it to rename a character is one
tool call, not two. The agent does not need to reason about what was previously selected
in these tabs; each call is independent of the others.

### Stateful entity: Scenes

Scenes work differently because rendering — the whole point of the agent's existence — is
a scene-scoped, multi-step operation that mirrors the Scenes tab's own selection-driven
UI. A scene must be **selected** (`select_scene`) or **created** (`create_scene`, which
selects it as a side effect) before anything else can happen to it. Once a scene is
selected, `update_scene`, `delete_scene`, `assign_character_to_scene`,
`assign_location_to_scene`, and `render_scene` all act on that selection implicitly —
none of them take a scene id. This matches the manual workflow exactly: a person can't
click Save, Delete, or Render on a scene without first clicking it in the list.

Practically, this means the agent's typical scene workflow is: resolve which scene is
meant (list, then select, or create) once per conversational topic, then issue as many
follow-up actions as needed against that selection without re-specifying it. If the
person's request shifts to a different scene, the agent selects that one before acting,
which changes the implicit target for everything after.

### Out of scope: rendering history and everything else

The agent can produce a new rendering, but it cannot browse a scene's past versions,
inspect one, delete one, or change which version is active — those stay exclusively
mouse-driven. This is a deliberate boundary, not a gap to fill later: version curation is
a judgment call over prose the person needs to read for themselves, and it sits downstream
of what a conversation can efficiently convey. The same is true of full-story
rendering/viewing/export/import, story archiving UI beyond the simple case below, and any
window chrome (panel layout, splitters, dialogs) — none of that is the application agent's
concern.

## Tool catalog

Parameter tables below describe intent, not a binding schema — types and required-ness
should follow the same conventions the existing coordinator tools use.

Character, Location, and Scene tools always act on the open story, with no `story_id`
parameter of their own — unlike the coordinator's equivalent tools, which accept an
optional `story_id` override because the coordinator has no notion of a story "on screen."
The application agent has exactly one story open at a time by construction; touching a
different story's data means opening it first via `open_story`.

### Story tools

**`list_stories`** — Find a story to open by title. Excludes archived stories unless asked
for them. Each result flags whether it is the story currently open in the window, so the
agent can tell "already open" apart from "needs `open_story`" without a separate check.
| param | description |
|---|---|
| `query` | Optional text to filter titles by. |
| `include_archived` | Include archived stories. Defaults to false. |

**`open_story`** — Make a story the open story. Switches the window to it: Story tab
active, Characters/Locations/Scenes populated, scene selection cleared.
| param | description |
|---|---|
| `story_id` | The story to open, from `list_stories`. |

**`create_story`** — Create a new story and open it immediately.
| param | description |
|---|---|
| `title` | Working title. |
| `story_brief` | Premise, situation, expected major events. |
| `style_guidance` | Voice, tense, POV, tone, pacing. |
| `generation_guidance` | Content boundaries or recurring generation rules. |

**`update_story`** — Update the open story's fields. Omitted fields are unchanged. Has no
`story_id` parameter — it always acts on whichever story is open.
| param | description |
|---|---|
| `title` | New title. |
| `story_brief` | New brief. |
| `style_guidance` | New style guidance. |
| `generation_guidance` | New generation guidance. |

**`archive_story`** / **`unarchive_story`** — Archive or unarchive the open story. No
parameters; acts on the open story.

### Character tools

**`list_characters`** — List the open story's characters (name + id), so the agent can
resolve a name to an id before acting on it.

**`create_character`** — Create a character in the open story. Switches to the Characters
tab and shows the new character.
| param | description |
|---|---|
| `name` | Character's name. |
| `description` | Appearance, personality, role. |
| `motive` | What they want; drives their actions. |

**`update_character`** — Update a character's fields. Switches to the Characters tab and
shows it. Omitted fields are unchanged.
| param | description |
|---|---|
| `character_id` | From `list_characters`. |
| `name`, `description`, `motive` | As above. |

**`delete_character`** — Delete a character. Switches to the Characters tab first so the
deletion is visible.
| param | description |
|---|---|
| `character_id` | From `list_characters`. |

### Location tools

Mirrors the character tools exactly, one tier simpler (no `motive` field):

**`list_locations`**, **`create_location`** (`name`, `description`),
**`update_location`** (`location_id`, `name`, `description`), **`delete_location`**
(`location_id`).

### Scene tools

**`list_scenes`** — List the open story's scenes (position, heading, id), for the agent to
find one to select. Each result flags whether it is the currently selected scene, so the
agent can tell "already selected" apart from "needs `select_scene`" without a separate
check.

**`select_scene`** — Select a scene as the current one. Switches to the Scenes tab, shows
the scene's detail and its cast/location assignments, and updates the Rendering pane to
that scene's versions. This is the prerequisite for every other scene tool below.
| param | description |
|---|---|
| `scene_id` | From `list_scenes`. |

**`create_scene`** — Create a scene in the open story and select it as a side effect
(equivalent to selecting it right after creation).
| param | description |
|---|---|
| `position` | Order within the story. Defaults to the end if omitted. |
| `heading` | Short label. |
| `brief` | Setting, characters, goals, constraints. |
| `required_actions` | Beats that must occur. |
| `desired_outcome` | State/decision/revelation expected by scene's end. |
| `target_length` | Guidance on length. |
| `pov_character_id` | POV character, from `list_characters`. |

**`update_scene`** — Update the selected scene's fields. No `scene_id` parameter — always
acts on the current selection. Omitted fields are unchanged.
| param | description |
|---|---|
| `heading`, `brief`, `required_actions`, `desired_outcome`, `target_length`, `pov_character_id` | As above. |

**`delete_scene`** — Delete the selected scene. No parameters.

**`assign_character_to_scene`** / **`unassign_character_from_scene`** — Add or remove a
character from the selected scene's cast.
| param | description |
|---|---|
| `character_id` | From `list_characters`. |

**`assign_location_to_scene`** / **`unassign_location_from_scene`** — Same, for locations.
| param | description |
|---|---|
| `location_id` | From `list_locations`. |

**`render_scene`** — Generate a new rendering for the selected scene and make it the
active version, the same as pressing Render. No parameters — it renders the current state
of the selected scene's brief, required actions, desired outcome, cast, and locations,
using the same context assembly the manual Render button uses.

This call is synchronous from the agent's point of view: it does not return until
generation (and the follow-on continuity-snapshot update) has finished, returning the
generated prose so the conversation can continue based on the actual result — approve it,
critique it, or fold feedback into another `update_scene` + `render_scene` pass. It can
fail the same way the manual button can: an earlier scene in the story has no active
rendering yet and must be rendered first.

## Example conversations

**Opening and editing:**
> "Open Ashwood Keep and change the tone to something darker."
`list_stories("Ashwood Keep")` → `open_story` → `update_story(style_guidance=...)`.

**Editing a character by name:**
> "Give Mara a reason to distrust Elias."
`list_characters()` → `update_character(character_id=<Mara>, motive=...)`.

**Driving a scene through feedback and re-rendering:**
> "Pull up the tunnel scene and make the collapse feel more dangerous, then render it."
`list_scenes()` → `select_scene(<tunnel scene>)` →
`update_scene(required_actions="...")` → `render_scene()` → agent reports the new prose
and asks whether it lands.

**Creating a scene from scratch:**
> "Add a new scene after this one where they surface into the flooded archive."
`create_scene(position=<next>, brief=...)` (selects it) → optionally
`assign_character_to_scene` / `assign_location_to_scene` → `render_scene()`.
