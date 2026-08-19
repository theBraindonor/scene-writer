---
archived: false
created_by: John Hoff
created_on: '2026-08-18T22:25:24Z'
name: c004-scene-rendering-agent
status: open
updated_by: John Hoff
updated_on: '2026-08-19T03:04:08Z'
---

# C004 — Scene Rendering Agent

## Scope

Implement the scene-rendering agent: a non-interactive, LLM-driven pipeline that generates a
scene's prose one scene at a time, using the story's structural data (scenario, style
guidance, scenes, characters, locations, and their assignments) plus the *active* renderings
of every prior scene as continuity context. Exposed through a new Textual TUI CLI command,
`scene-coordinator render`, with a scene-details pane and a rendering-output pane.

This campaign builds on `c003-coordinating-agent`'s shared LLM-runtime infrastructure
(`scene.agent.config`/`llm`/`registry`/`role`) and reuses the `Rendering` model and
`scene.core.rendering` service already delivered in `c002-initial-data-model-and-crud`. It
does not touch the coordinator's tool-calling chat loop (`scene.agent.coordinator`) at all —
rendering is a separate, simpler, non-conversational pipeline with its own agent module,
sharing only the LLM-runtime layer underneath.

Out of scope: editing story/scene/character/location structural data (that remains the
coordinator's job — this TUI reads structural data but only creates/activates renderings),
and any tool-calling on the rendering agent's part (it makes plain completion calls with no
tools).

## Design decisions

- **Non-interactive, reconstructed-context generation — not a chat agent.** Each generation
  request is a single, fresh `messages` list built from scratch, not a persisted/growing
  conversation: a system message with the story's scenario and style guidance, then one
  user/assistant message pair per scene strictly before the target scene (user: that scene's
  full detail — heading, description, required actions, length, assigned characters and
  locations; assistant: that scene's current *active* rendering body), and a final user
  message asking the model to write the target scene. This is deliberate, per the developer's
  explicit direction: a real chat history would keep rejected or since-replaced renderings in
  context once generated, even after a different version was activated. Rebuilding context
  from the database's currently-active renderings on every call means switching which
  rendering is active for an earlier scene transparently changes the continuity context for
  every later regeneration, with no separate invalidation step.
- **Two render actions, one context-construction path.** "Render next scene" targets the
  lowest-position scene in the story that has no active rendering yet (sequential, forward
  only). "Regenerate this scene" targets whichever scene is currently selected, even if it
  already has an active rendering, producing an additional `Rendering` row rather than
  overwriting the existing one. Both actions build context identically: every scene strictly
  before the target, using each one's active rendering. A newly created rendering becomes the
  scene's active one immediately (`scene.core.rendering.create_rendering` +
  `set_active_rendering`), consistent with how `c002` designed the one-active-rendering-per-
  scene model.
- **Plain completion, not tool-calling.** The rendering agent calls `scene.agent.llm`'s
  existing `complete`/`stream_complete` with no `tools` argument — it never edits structural
  data, so it needs no tool registry, dispatch loop, or `Tool` schema/handler pattern from
  `scene.agent.coordinator.loop`. A new, small module in `scene.agent` (sibling to
  `coordinator`, not inside it) owns message construction and streaming.
- **Reuses the existing `RENDERING` agent role and model registry seam.** `AgentRole.RENDERING`
  / `SCENE_RENDERING_AGENT` was reserved but unconsumed since `c003`; this campaign is what
  finally reads it via `get_llm_config(AgentRole.RENDERING)`, letting the rendering agent run
  on a different model profile (e.g. a role-play-tuned model) than the coordinating agent,
  swappable independently via `.env`.
- **`scene-coordinator render` — no story id argument, in-TUI story picker.** Consistent with
  the coordinator chat CLI's philosophy (`c003`/`e005`): the command takes no arguments: it
  opens directly to a story picker (listing existing stories via `scene.core.story.list_stories`),
  and only after a story is chosen does the two-pane render view appear. This is a separate
  Textual `App` from `CoordinatorApp` (a distinct command, distinct concerns), though it may
  share small pieces of that module's established patterns (message-block styling,
  streaming-event handling) where directly applicable.
- **Two-pane TUI layout.** A left-hand pane lists the story's scenes in order with their
  render status (rendered/unrendered, and which rendering is active), and shows the currently
  selected scene's full detail (heading, description, required actions, length, cast,
  locations). A right-hand pane shows the rendering output: live-streamed text while a
  generation is in progress (consistent with the coordinator TUI's existing streaming
  precedent from `e005a`), and, once scenes have renderings, a way to browse a selected
  scene's full rendering history and activate a different one (`list_renderings` /
  `set_active_rendering` / `delete_rendering` from `scene.core.rendering`) — explicitly in
  scope for this campaign, rather than deferred to the `scene-data` CLI, so a writer never has
  to leave the render TUI to compare or switch versions.
- **Sequencing implication of "render next scene."** Because generation always targets the
  lowest-position scene without an active rendering, a story's scenes are always rendered
  first-to-last on their first pass; there's no "render scene 3 before scene 1" first-render
  path. Regenerating an earlier scene after later ones exist does not retroactively touch
  those later scenes' already-generated content — only a subsequent regeneration of a later
  scene would pick up the newly active earlier rendering, per the reconstructed-context design
  above.

## Log
