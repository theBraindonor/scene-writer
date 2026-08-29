---
archived: false
campaign: c009-post-v2-polish
created_by: John Hoff
created_on: '2026-08-29T16:14:17Z'
depends_on: []
kind: scripted
name: c009-scene-editor-ui-tweaks
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-29T17:09:16Z'
---

# Scene editor UI tweaks

## Requirements

In `src/scene/gui/entity_column/scenes.py` (the scene editor panel):

1. The scene selector list (`list_widget`) must show at most 4 scenes before it
   starts scrolling, instead of the current default of 6.
2. The Position spin box and Point of View combo box must not change their
   value when the user scrolls the mouse wheel over them incidentally — they
   should only respond to the wheel once the widget already has keyboard
   focus (i.e. after being explicitly clicked into).
3. The "New Scene" text button is replaced by a small "+" icon button placed
   to the right of the "Scenes" section heading, with a tooltip reading
   "New Scene".
4. The Save and Delete buttons move from below the detail form to directly
   below the scene selector list, right-justified.
5. Save and Delete are both disabled whenever no scene is selected.
6. Save is additionally disabled until the selected scene has unsaved field
   changes (heading, position, brief, required actions, POV character,
   desired outcome, or target length) — i.e. it starts disabled right after a
   scene loads or is saved, and enables only once the user edits a field.

## Rationale

The user has repeatedly changed a scene's Position or POV character by
accident while scrolling past those fields with the mouse, since both widgets
currently accept wheel input just from being moused over. The scene list
scrolling after 6 items also shows more of the list than intended for quick
navigation; 4 keeps the visible set tighter. Relocating New/Save/Delete next
to the heading and selector (rather than below a long form) keeps primary
actions reachable without scrolling past the whole form, and disabling
Save/Delete when there's nothing to act on (or nothing changed to save)
prevents accidental no-op or destructive clicks.

## Plan

1. Add a small reusable module, e.g. `src/scene/gui/scroll_guard.py`, with
   `NoScrollSpinBox(QSpinBox)` and `NoScrollComboBox(QComboBox)` subclasses
   that override `wheelEvent` to ignore the event unless `self.hasFocus()` is
   already true, falling through to the base implementation otherwise. Use
   these in place of the plain `QSpinBox`/`QComboBox` for `position_edit` and
   `pov_character_combo` in `scenes.py`.
2. In `scenes.py`, change the "Scenes" heading row to a `QHBoxLayout`
   containing `section_heading("Scenes")`, a stretch, and a new fixed-width
   `QPushButton("+")` (replacing the old text `new_button`) with
   `setToolTip("New Scene")`, wired to the existing `_on_new_clicked`.
3. Change the `fit_list_height_to_contents` call for `self.list_widget` to
   pass `max_visible_rows=4`.
4. Move `save_button`/`delete_button` out of the bottom `buttons` layout (which
   still exists for consistency with `characters.py`/`locations.py`, or is
   removed and its remaining widgets — none other are needed there — cleaned
   up) into a new `QHBoxLayout` placed immediately after `list_widget` and
   before `form`, with a leading stretch so the buttons are right-justified.
5. Add a `self._dirty` bool and `self._loading_detail` guard bool. In
   `_load_detail`, wrap the field-population code with `_loading_detail`
   set `True`/`False` so programmatic population doesn't count as a change.
   Connect the relevant change signals (`textChanged`/`valueChanged` for line
   edits and spin box, `textChanged` for the plain text edits,
   `currentIndexChanged` for the POV combo) to a handler that sets
   `self._dirty = True` and refreshes button state, but only when
   `not self._loading_detail`.
6. Add a `_update_button_states()` helper — `delete_button.setEnabled(...)`
   true iff `current_scene_id is not None`; `save_button.setEnabled(...)` true
   iff additionally `self._dirty`. Call it after `_load_detail`, after a
   successful save (which also resets `self._dirty = False`), and after
   delete/refresh.
7. Update `test/scene/gui/entity_column/test_scenes.py` to cover: the list's
   max-visible-rows of 4, the wheel guard ignoring an unfocused wheel event on
   both widgets, the "+" button's tooltip text and that it still creates a new
   scene, and the Save/Delete enablement transitions (no selection → both
   disabled; select a scene → Delete enabled, Save disabled; edit a field →
   Save enabled; save → Save disabled again).

## Verification

- `pdm run pytest` passes, including the new/updated cases in
  `test/scene/gui/entity_column/test_scenes.py`.
- `pdm run lint` is clean.
- Launch the app with `pdm run scene-writer`, open a story with 5+ scenes, and
  manually confirm: the scene list scrolls after 4 items; scrolling the mouse
  wheel over Position/POV while just hovering (not focused) does not change
  their value, but does after clicking into them; the "+" button sits next to
  the "Scenes" heading and shows the "New Scene" tooltip; Save/Delete sit
  right-justified below the scene list and are disabled with no scene
  selected, Delete enables on selection, and Save enables only after editing
  a field and disables again after saving.

## Log

### Review - 2026-08-29T16:16:26Z - John Hoff

Reviewed against the two applicable world-assigned lore items (linting, unit-testing): the Plan and Verification honor both — lint is checked in Verification, and the primary test file update correctly mirrors src/scene/gui/entity_column/scenes.py per the unit-testing convention, with all tests required to pass. One minor gap: the new src/scene/gui/scroll_guard.py module isn't given its own mirrored test file (test/scene/gui/test_scroll_guard.py) — its behavior is only exercised indirectly via test_scenes.py, which is likely sufficient in substance but diverges from the stated mirroring convention; consider adding a dedicated test file or explicitly noting the indirect-coverage choice. Also noting, separately from lore compliance, that the gui region's description ('Not yet implemented') appears stale given that scenes.py already exists in the form the Plan assumes. PASS-WITH-NOTES.

### Message - 2026-08-29T16:44:47Z - John Hoff

Implementation deviation from Plan: the wheel-guard subclasses initially only overrode wheelEvent() checking hasFocus(), which was insufficient — QSpinBox/QComboBox default to Qt::WheelFocus, which grants focus as a side effect of Qt's normal wheel-event dispatch before wheelEvent() runs, so hasFocus() was always true and hovering + scrolling still changed the value. Fixed by also setting focusPolicy to Qt::StrongFocus in each subclass's __init__ to remove the wheel-grants-focus behavior, keeping click/tab focus intact. Rewrote test/scene/gui/test_scroll_guard.py to dispatch via QApplication.sendEvent() instead of calling wheelEvent() directly, since a direct call bypasses Qt's focus-granting step and would not have caught this bug. Also adjusted the "+" new-scene button per user follow-up: left-justified immediately next to the "Scenes" heading (not pushed to the far right) and styled larger/bold/green via a stylesheet for visibility.

### Completed - 2026-08-29T17:09:16Z - John Hoff

Verified: pdm run pytest (496 passed) and pdm run lint clean. User confirmed the running app visually after the wheel-guard fix and plus-button styling follow-up.
