---
archived: false
campaign: c005-initial-gui-application
created_by: John Hoff
created_on: '2026-08-21T18:48:03Z'
depends_on: []
kind: scripted
name: e007-left-column-chat-and-fifty-fifty-split
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-21T20:35:08Z'
---

## Requirements

Rework `MainWindow`'s (`src/scene/gui/main_window.py`) top-level layout so it's built around two
even columns instead of a splitter-plus-full-width-chat-bar:

1. **The chat panel moves into the left-hand column.** `ChatPanel` no longer spans the full width
   of the window as a bar docked below the splitter; it becomes part of the same left column as
   the entity column, stacked beneath it, so it only ever occupies the left half's width.
2. **Within the left column, the entity column's tabs are the element that grows.** As the window
   is resized taller/shorter, the entity column (and specifically the Story/Characters/Locations/
   Scenes tab widget it shows once a story is loaded) expands to consume the available vertical
   space in the left column; the chat panel keeps to its own natural height and does not grow to
   soak up extra space.
3. **The left and right columns are each 50% of the window's width**, and stay that way as the
   window is resized — not just correct at initial layout, but maintained on every resize.

This is explicitly a first pass at the high-level container layout — further adjustments are
expected in follow-up encounters once the developer has verified it live. Out of scope for this
encounter: any change to what each region contains, how entities are edited, how the rendering
column displays content, or how the chat panel drives the coordinating agent — this is purely a
container/sizing/nesting change, not a features change.

## Rationale

The developer wants to understand and control how the application's containers grow: the chat
interface should live inside the left-hand column rather than spanning the whole application
width, the story editor's tabs (not the chat panel) should be the part of that column that
expands, and the left/right columns should split the window evenly. The developer noted this is a
starting point they expect to keep adjusting once they can see it running, so this encounter
covers only the three changes above.

## Plan

1. **Update `src/scene/gui/main_window.py`**:
   - Add a plain `QWidget` left-column container (`self.left_column`) with its own `QVBoxLayout`
     (zero content margins, so no new visual padding versus today). Add `self.entity_column` to it
     with stretch factor `1` and `self.chat_panel` with stretch factor `0`, so the entity column
     (and therefore its internal tab widget, since `EntityColumn`'s own layout has that tab widget
     as its sole stacked child once a story loads) consumes all extra vertical space while the
     chat panel sizes to its own sizeHint/minimumSizeHint instead of growing.
   - Change `self.splitter` to add `self.left_column` and `self.rendering_column` (instead of
     adding `entity_column` directly to the splitter and `chat_panel` separately below it in the
     central layout).
   - Set the splitter to an even 50/50 split that holds across resizes: `self.splitter.setSizes([1,
     1])` (Qt normalizes this list proportionally against the actual available width at layout
     time) plus `self.splitter.setStretchFactor(0, 1)` and `self.splitter.setStretchFactor(1, 1)`
     on the two panes, so any extra or reclaimed width from resizing the window is always divided
     evenly between them.
   - Update the central widget's top-level `QVBoxLayout` to just `story_header` then `splitter`
     (the chat panel is no longer added there directly).
   - Update the `MainWindow` class docstring (currently "Four-region application shell: story
     header, entity column, rendering column, chat panel") to describe the new shape: a header,
     a left column (entity column tabs + chat panel), and a right column (rendering column).
2. **No changes needed inside `EntityColumn`, `ChatPanel`, or `RenderingColumn` themselves** —
   `EntityColumn`'s single stacked child already expands to fill whatever space `EntityColumn`
   itself is given, so giving `EntityColumn` the vertical stretch inside the new left column is
   sufficient to make its tabs the growing element; no internal size-policy changes are required.
3. **Update `test/scene/gui/test_main_window.py`**:
   - Add a test asserting `window.chat_panel` and `window.entity_column` are both parented under
     `window.left_column` (e.g. `window.chat_panel.parentWidget() is window.left_column` and
     `window.entity_column.parentWidget() is window.left_column`), confirming the chat panel is no
     longer a direct child of the central layout spanning the window.
   - Add a test that resizes the window to at least two different widths (e.g. 1000px then
     1200px) and asserts `window.splitter.sizes()` stays within a small pixel tolerance of an even
     split at both widths, verifying the 50/50 split is maintained across resizes rather than only
     correct at initial construction.
   - Add a test that, after selecting a story (so the entity column's tabs are showing), asserts
     `window.entity_column.height()` is greater than `window.chat_panel.height()` within the shared
     left column, confirming the entity column's tabs — not the chat panel — receive the extra
     vertical space.
   - Existing tests referencing `window.chat_panel.input_edit`/`turn_completed` need no changes,
     since `ChatPanel`'s own attributes and behavior are unchanged — only its position in the
     widget tree moves.

## Verification

- `pdm run pytest` — full suite passes, including the new/updated `test_main_window.py`
  assertions on the left column's composition and the splitter's persistent 50/50 split.
- `pdm run lint` — clean.
- Manually launch `pdm run scene-writer`, resize the window, and confirm: the chat panel appears
  within the left-hand column beneath the entity column's tabs (never spanning the full window
  width); the tabs visibly grow/shrink to fill the available vertical space in the left column as
  the window is resized, while the chat panel's height stays roughly constant; and the left/right
  columns stay visually even (about half the window's width each) as the window is resized wider
  or narrower.

## Log

### Review - 2026-08-21T19:41:47Z - John Hoff

This scripted encounter's Plan is well-scoped to its stated Requirements (moving the chat panel into the left column, giving the entity column's tabs vertical stretch priority, and locking the splitter to a persistent 50/50 width split) and stays within the `gui` region's path (`src/scene/gui`) plus its test mirror (`test/scene/gui`); it explicitly satisfies both applicable lore items — `linting` via a required clean `pdm run lint` in Verification, and `unit-testing` via three new, behavior-specific assertions added to the correctly-mirrored `test/scene/gui/test_main_window.py` plus a required full `pdm run pytest` pass — with no gaps, conflicts, or unverifiable concerns found within the reviewed surface.

### Message - 2026-08-21T19:59:59Z - John Hoff

Manual verification found a further layout gap beyond the Plan: the StoryHeader (story label + New/Open buttons) was left as a full-width row above the splitter, but it needs to reside inside the left-hand column too, not span the whole window. Moving it into `left_column`'s layout, above `entity_column`, alongside the already-relocated `chat_panel`. Central widget's top-level layout becomes just the splitter. No change to StoryHeader's own behavior — purely a reparenting/placement fix consistent with this encounter's "chat interface should be part of the core left-hand column" intent, now extended to the story header for the same reason.

### Message - 2026-08-21T20:11:24Z - John Hoff

Two more refinements from manual verification, applied during this encounter's execution: (1) each entity tab's content (StoryDetailWidget, CharactersWidget, LocationsWidget, ScenesWidget) previously had its expandable fields (QPlainTextEdit, etc.) stretch to fill all leftover vertical space in the tab, since nothing absorbed that space instead; added a trailing `layout.addStretch()` to each of the four widgets' top-level layout so content keeps its natural size and any extra space becomes blank space below it, rather than stretching the fields themselves. (2) The chat panel's transcript area was too short now that it sizes to its own preferred height rather than stretching; set `ChatPanel.transcript_scroll`'s minimum height to 140px (roughly double its prior ~70px), doubling the visible chat-history space as requested. Neither change affects data flow, signals, or the container/sizing/nesting intent of the original Plan.

### Message - 2026-08-21T20:25:22Z - John Hoff

Added draggable dividers per developer request: the horizontal splitter (left/right columns) and a new vertical QSplitter between the entity column and chat panel (replacing the plain QVBoxLayout stretch factors used for that pairing) are both real QSplitters, so the developer can drag either handle by hand. Behavior: the horizontal split defaults to an even 50/50 and re-asserts that on every window resize only until the developer drags it (detected via splitterMoved, which fires solely on a real drag, not on programmatic setSizes) — after that, Qt's native splitter resize behavior takes over and preserves the developer's chosen ratio. The vertical split defaults to the chat panel at its preferred height with the entity column absorbing the rest, and needs no such tracking: with the entity column's stretch factor at 1 and the chat panel's at 0, Qt already keeps the chat panel pinned at whatever height it currently has — default or user-dragged — while the entity column alone absorbs any extra space from a window resize, both before and after a drag. Added `test_left_column_composition`, `test_dragging_horizontal_splitter_persists_across_resizes`, and `test_chat_panel_height_stays_pinned_across_resizes_until_dragged` to `test_main_window.py` to cover this. `pdm run lint` clean, full `pdm run pytest` suite passes (369 tests, up from 367).

### Message - 2026-08-21T20:32:59Z - John Hoff

Fixed a gap in the chat panel's own collapse toggle: hiding `content_widget` shrinks `ChatPanel`'s sizeHint, but the vertical splitter doesn't automatically shrink a pane to match a shrunken sizeHint — its pixel sizes stay fixed until explicitly told otherwise, so collapsing just left blank space instead of returning it to the entity column. Added `ChatPanel.collapse_toggled(bool)`, emitted from `_on_toggle_expanded`; `MainWindow` connects it to `_on_chat_collapse_toggled`, which resizes `vertical_splitter` explicitly: giving the entity column the reclaimed space on collapse, and restoring the chat panel's pre-collapse height (its manually-dragged height if the developer had dragged it, otherwise its default sizeHint height) on expand. Added `test_toggle_button_emits_collapse_toggled` to `test_chat_panel.py`, and `test_collapsing_chat_panel_gives_its_space_to_entity_column`/`test_collapsing_chat_panel_restores_a_manually_dragged_height_on_expand` to `test_main_window.py`. `pdm run lint` clean, full `pdm run pytest` suite passes (371 tests, up from 369) — one unrelated Textual CLI test flaked and passed on isolated re-run.

### Completed - 2026-08-21T20:35:08Z - John Hoff

Verification passed: pdm run lint clean, full pdm run pytest suite green (371 tests; one unrelated Textual CLI test flaked once and passed on isolated re-run), and pdm run scene-writer launches and behaves correctly. Final shape after live iteration: chat panel and story header both moved into the left column; entity column tabs keep natural content size (no forced stretch) with blank space absorbing the rest; chat transcript height doubled; both the left/right column split and the entity/chat split are real draggable QSplitters (horizontal defaults to 50/50 and self-corrects until dragged, vertical keeps chat pinned at its current height by default or by drag); and the chat panel's own collapse toggle now actually resizes the container, handing its space to the entity column and restoring it (including any dragged height) on re-expand.
