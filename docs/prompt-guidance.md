# Scene Writer prompt guidance

## Purpose

This document defines the prompt strategy for generating a continuing fictional story
from ordered scenes. It is designed to work with hosted models and smaller self-hosted
models, without requiring a large JSON state schema.

The strategy separates two jobs:

1. A **scene-writing model** creates the prose for one scene.
2. A **continuity-editor model** updates the compact narrative state after an accepted
   scene.

The models may be the same model or two different models. The continuity editor should
be selected for reliable factual extraction and conservative editing; it does not need
the same creative strengths as the scene writer.

## Core workflow

```text
Story reference + prior continuity snapshot + scene brief
                         |
                         v
                  Scene-writing model
                         |
                         v
                New scene rendering (prose)
                         |
                         v
Prior continuity snapshot + accepted scene rendering
                         |
                         v
                 Continuity-editor model
                         |
                         v
              New continuity snapshot (text)
```

The application persists the prose in `rendering.body` and the resulting text state in
`continuity_snapshot.narrative_state`. Only an active rendering should be used as
continuity source material.

## Prompt context

The scene writer does not need the full novel on every request. Construct its prompt
from the smallest context that accurately supports the requested scene.

### Stable story reference

Use the human-authored story and reference records:

- `story.story_brief`: premise, overall situation, and expected major direction.
- `story.style_guidance`: voice, tense, tone, pacing, and other style direction.
- `story.generation_guideance`: additional generation constraints, such as content
  boundaries, recurring rules, or language restrictions.
- Assigned characters: names, enduring descriptions, and motives.
- Assigned locations: names and enduring descriptions.

Do not let generated state updates overwrite this human-authored reference material.

### Mutable continuity context

Include the snapshot through the immediately preceding accepted scene. It holds only
short-lived or changing facts: location, current condition, revealed knowledge,
possession, relationship changes, elapsed time, and open threads.

Do not send every prior scene by default. Include the preceding active rendering only
when exact voice, physical detail, or a cliffhanger needs to carry directly into the
next scene. Summaries or the continuity snapshot are normally sufficient for older
scenes.

### Scene-specific request

Build the current request from:

- `scene.brief`
- `scene.required_actions`, when present
- `scene.pov_character_id`, when present
- `scene.desired_outcome`, when present
- `scene.target_length`, when present
- Assigned characters and locations relevant to the scene

`required_actions` describes events or beats that must occur. `desired_outcome`
describes what should be different at the end of the scene. They are complementary.

## Use compact prose cards for the scene writer

For smaller models, compact labeled prose is usually more efficient and robust than a
large JSON object. The application may store reference data relationally but should
render only the relevant records into simple cards.

```text
CHARACTER: Mara
Enduring details: Practical, observant, reluctant to rely on others.
Core motive: Find her brother before the magistrate does.

CURRENT STATE
Location: Abandoned rail station platform.
Condition: Tired; uninjured.
Knowledge: Elias hid the map; his reason remains unknown.
Relationship with Elias: Distrustful but cooperating.

LOCATION: Abandoned rail station
A soot-stained, partially collapsed station. The eastern tunnel begins below the
platform. Sounds travel sharply through the tiled underpass.
```

Limit the prompt to characters and locations assigned to the scene, plus any directly
relevant off-page facts. Do not serialize raw database rows for the writer.

## Continuity snapshot format

`continuity_snapshot.narrative_state` is one text field. Keep it concise, factual, and
easy for a small model to update. Bullets or short labeled paragraphs are preferred.

```text
CURRENT CANON — after Scene 6

Mara: At the abandoned rail station. Tired but uninjured. Knows Elias hid the map;
does not know why. Distrusts him but will cooperate to reach the archive.

Elias: At the abandoned rail station, carrying the map. Needs Mara's help to pass
through the tunnel. His connection to the magistrate remains secret.

Rail station: The eastern tunnel is accessible from the platform.

Open threads:
- Why Elias hid the map.
- Identity of the unseen pursuer.
- Elias's connection to the magistrate.
```

The snapshot is an operational aid, not a comprehensive recap. Omit static information
already supplied by character and location records, and omit prose-level detail that
does not affect future scenes.

## Scene-writing prompt template

Use stable instructions at the application/developer level when the API supports
message roles. Send the scene-specific material as the current user request. For a
simple local interface without message roles, concatenate the sections in the same
order and clearly label them.

```text
You are the prose writer for a continuing fictional narrative.

Write the requested scene as immersive fiction. Preserve established canon, character
knowledge, relationships, physical details, chronology, and unresolved consequences.

Requirements:
- Use the requested point of view and tense.
- Dramatize through action, sensory detail, dialogue, and interiority.
- Do not resolve a major plot thread unless the scene brief explicitly requires it.
- Do not introduce new named characters, world rules, abilities, or backstory facts
  unless the scene brief authorizes them.
- End at a meaningful turn, decision, revelation, complication, or emotional shift.
- Return fiction prose only. Do not explain your process or restate these materials.

STORY REFERENCE
{story_brief}
{style_guidance}
{generation_guideance}
{relevant_character_cards}
{relevant_location_cards}

CURRENT CANON
{prior_narrative_state}

OPTIONAL RECENT PROSE
{previous_active_rendering}

SCENE BRIEF
Heading: {heading}
Point of view: {pov_character}
Brief: {brief}
Required actions: {required_actions}
Desired outcome: {desired_outcome}
Target length: {target_length}
```

Omit empty optional fields rather than emitting placeholders. The application should
set a practical output limit that matches `target_length`.

## Continuity-editor prompt template

The continuity editor receives the prior text state and the newly accepted scene. It
returns a replacement text state, not commentary and not fiction.

```text
You are the continuity editor for a serialized novel.

Given the current canonical narrative state and one newly accepted scene, write the
updated canonical narrative state.

Rules:
- Preserve all prior facts unless the new scene explicitly changes them.
- Add only facts directly stated or unambiguously shown in the scene.
- Do not infer unstated motives, identities, timelines, or future events.
- Do not resolve an open thread unless the scene explicitly resolves it.
- Keep the result concise and factual, using the supplied snapshot format.
- Return the updated narrative state only. Do not include analysis, explanations, or
  the scene prose.

CURRENT CANONICAL NARRATIVE STATE
{prior_narrative_state}

ACCEPTED SCENE
{active_rendering_body}
```

The application may show the resulting snapshot to the user for review before it is
used as canon. This is especially useful when a small model may over-infer from prose.

## Revision and invalidation

An active rendering determines the continuity snapshot for its scene. If the user
selects a different active rendering for Scene *N*, the snapshot through Scene *N* and
all later snapshots are stale. Regenerate them in narrative order before using them to
write or revise later scenes.

```text
Active rendering changed for Scene N
        |
        v
Invalidate snapshots through Scenes N, N+1, ...
        |
        v
Regenerate snapshots from Scene N forward using active renderings
```

Do not mutate human-authored story briefs, character records, location records, or
scene briefs during this regeneration process.

## Implementation safeguards

- Persist every scene rendering separately; do not overwrite an earlier draft.
- Use only the selected active rendering as continuity input.
- Keep continuity snapshots short enough to fit comfortably alongside the current
  scene's references and requested output.
- Prefer explicit facts over interpretive summaries.
- If the continuity editor contradicts known canon, flag the result for review rather
  than silently treating the new statement as fact.
- Consider JSON change sets only later, if the application needs automated fact
  validation or rich querying. They are not required for the initial text-ledger
  approach.
