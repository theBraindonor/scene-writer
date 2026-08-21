---
archived: false
campaign: c005-initial-gui-application
created_by: John Hoff
created_on: '2026-08-21T04:48:50Z'
depends_on: []
kind: scripted
name: e006-story-header-and-tabbed-entity-column
regions:
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-21T18:36:23Z'
---

## Requirements

Rework the GUI's story-selection and entity-editing UI within `src/scene/gui`:

1. **Eliminate the collapsible story-list sidebar entirely.** `Sidebar` (`src/scene/gui/sidebar.py`), its `story_list`, `collapse_button`/`collapse_toggled`, and the splitter-pane-width-driving logic in `MainWindow` (`SIDEBAR_PANE_INDEX`, `DEFAULT_SIDEBAR_WIDTH`, `_sidebar_expanded_width`, `_on_sidebar_collapse_toggled`) are removed. The main splitter goes from three panes (sidebar, entity column, rendering column) to two (entity column, rendering column).
2. **Replace it with a compact story header.** A new always-visible header row shows the current story's title (or a "no story selected" placeholder) plus two buttons: **"New Story"** (unchanged creation flow — the existing `NewStoryDialog`, prompting for title/scenario/style guidance and creating + auto-selecting the result) and **"Open"**.
3. **"Open" launches a modal story picker.** The modal lists stories from the database (excluding archived by default), with a checkbox in its bottom-left corner labeled to include archived stories — checking it re-populates the list to include them, unchecking excludes them again. Bottom-right holds Cancel and OK. OK is only enabled once a story is selected; confirming with OK selects that story (same effect as the old sidebar's row-click selection — updates the header label, `MainWindow.current_story_id`, `CoordinatorState.current_story_id`, and cascades to the entity/rendering columns via the existing `current_story_changed` signal). Cancel (or closing the dialog) leaves the current selection untouched.
4. **The entity column becomes tab-based.** `EntityColumn` (`src/scene/gui/entity_column/column.py`) replaces its single scrolling stack of stacked sections (story detail, scenes, characters, locations) with a `QTabWidget` of exactly four tabs, in this order: **Story**, **Characters**, **Locations**, **Scenes**. Each tab hosts the existing corresponding widget (`StoryDetailWidget`, `CharactersWidget`, `LocationsWidget`, `ScenesWidget`) unchanged in behavior, each within its own scroll area. The existing "no story selected" empty-state page is preserved (shown via the same outer `QStackedWidget` pattern, just swapping the tab widget in for the old scrollable content widget as the stack's second page). All four widgets keep loading eagerly on `set_story` regardless of which tab is active, exactly as today — no lazy-loading is introduced.
5. Update `README.md`'s GUI section (currently describes "a collapsible sidebar for picking or creating a story" and "creating a story from the sidebar") to describe the new header/modal picker and the tabbed entity column instead.

Out of scope: any change to `scene.core`/`scene.data`, to the rendering column, to the chat panel, or to what data each entity tab can edit (this is a layout/navigation change only, not a features change).

## Rationale

The developer asked to remove the collapse/expand story-picker pane in favor of a lighter-weight "Open" button next to the story label that launches a modal selector (with an archived-inclusion checkbox and Cancel/OK), and to reorganize the entity column's four sections (Story, Characters, Locations, Scenes) into tabs instead of a single long scrolling stack. Clarified with the developer that "New Story" stays as its own button next to "Open" in the header, rather than folding creation into the picker modal.

## Plan

1. **Add `src/scene/gui/story_header.py`**, replacing `src/scene/gui/sidebar.py` (delete the old file):
   - Move `NewStoryDialog` here unchanged.
   - Add `StoryPickerDialog(QDialog)`: a `QListWidget` of stories (id in `Qt.ItemDataRole.UserRole`, title as label) loaded via `scene.core.story.list_stories(session, include_archived=...)`; a `QCheckBox` ("Include archived") bottom-left that re-runs the query and repopulates the list on toggle; a `QDialogButtonBox` (Ok/Cancel) bottom-right, with the Ok button disabled until a list row is selected (wire via the list's `currentItemChanged`/`itemSelectionChanged`); `accepted`/`rejected` wired to `accept`/`reject` as `NewStoryDialog` already does. Expose `selected_story_id() -> int | None` reading the current item's stored id.
   - Add `StoryHeader(QWidget)`: `story_label` (QLabel), `new_story_button`, `open_button`, laid out in one row (label, stretch, New Story, Open). Signal `story_selected = Signal(object)` (`int`). `set_current_story(story_id: int | None)` loads the story via `scene.core.story.get_story` and updates the label text (to the title, or a placeholder like "No story selected" when `story_id` is `None` or not found) — this method only updates display and never emits `story_selected`, so callers can sync the label after a selection made elsewhere without feedback loops. `_on_new_story_clicked` mirrors `Sidebar._on_new_story_clicked`/`_prompt_new_story` today (kept as a `_prompt_new_story` method for the same monkeypatch-based testing pattern the current sidebar tests use), creates the story via `scene.core.story.create_story`, then emits `story_selected(story_id)`. `_on_open_clicked` delegates to a `_prompt_story_picker` method (constructs `StoryPickerDialog`, returns `selected_story_id()` if accepted else `None` — kept as its own method for the same monkeypatchable-in-tests reason), and emits `story_selected(story_id)` when it returns non-`None`.
2. **Update `src/scene/gui/main_window.py`**: replace `self.sidebar = Sidebar()` with `self.story_header = StoryHeader()`; connect `story_header.story_selected` to `_on_story_selected`. Remove `SIDEBAR_PANE_INDEX`/`DEFAULT_SIDEBAR_WIDTH` module constants, `_sidebar_expanded_width`, and `_on_sidebar_collapse_toggled`. Replace the `header_layout` (which held `collapse_button`) with `self.story_header` added directly to the central `QVBoxLayout`. Change the splitter to only add `entity_column` and `rendering_column`. In `_on_story_selected`, after setting `current_story_id`/`coordinator_state.current_story_id`, call `self.story_header.set_current_story(story_id)` before emitting `current_story_changed`. Simplify `_on_chat_turn_completed`: when the agent's `current_story_id` differs from the window's, just call `self._on_story_selected(agent_story_id)` directly (no list-refresh step is needed anymore since there's no list to keep in sync) instead of the old `self.sidebar.refresh_stories(...)`.
3. **Update `src/scene/gui/entity_column/column.py`**: keep `story_detail`/`scenes`/`characters`/`locations` attributes and their existing cross-wiring (`scene_selected`, `characters_changed`/`locations_changed` → `refresh_assignment_options`) unchanged. Replace the single `QScrollArea`-wrapped `content` `QWidget` with a `QTabWidget` (`self.tabs`) with four tabs — "Story" → `story_detail`, "Characters" → `characters`, "Locations" → `locations`, "Scenes" → `scenes` — each wrapped in its own `QScrollArea` (`setWidgetResizable(True)`). Swap the second `QStackedWidget` page from the old scroll-wrapped content to `self.tabs`; update `set_story` to target it (`self.stack.setCurrentWidget(self.tabs)`).
4. **Update `README.md`**'s GUI section: describe the header row (story label, "New Story", "Open" launching the modal picker with its archived-inclusion checkbox) in place of "a collapsible sidebar for picking or creating a story," describe the tabbed entity column (Story/Characters/Locations/Scenes) in place of the single-column description, and change "creating a story from the sidebar" to reference the header instead.
5. **Update tests**:
   - Replace `test/scene/gui/test_sidebar.py` with `test/scene/gui/test_story_header.py`: tests for `StoryHeader` (default label text, `set_current_story` updating the label without emitting `story_selected`, the New Story flow via a monkeypatched `_prompt_new_story` emitting `story_selected` and updating the label, a declined New Story prompt leaving the label unchanged) and for `StoryPickerDialog` directly (default list excludes archived stories, checking "include archived" repopulates the list to include them and unchecking removes them again, the Ok button's enabled state tracks list selection, `selected_story_id()` returns the selected row's id).
   - Update `test/scene/gui/entity_column/test_column.py` to assert the four tabs exist in the required order (`widget.tabs.tabText(i)` for `i in range(4)` equals `["Story", "Characters", "Locations", "Scenes"]`) and that `widget.stack.currentWidget() is widget.tabs` once a story is set; existing assertions against `widget.story_detail`/`widget.scenes`/`widget.characters`/`widget.locations` need no changes since those attributes are unchanged.
   - Update `test/scene/gui/test_main_window.py`: replace every `window.sidebar.story_list.setCurrentRow(N)` call with directly emitting `window.story_header.story_selected.emit(story_id)` (using the relevant seeded story's id) via a small local helper; replace the New-Story test's monkeypatch/assertions to target `window.story_header._prompt_new_story`/`window.story_header.new_story_button`/`window.story_header.story_label.text()`; replace the chat-creates-a-story test's sidebar-list assertion with a `window.story_header.story_label.text()` assertion; delete `test_collapse_toggle_drives_sidebar_pane_width_to_zero_and_back` (the feature it tests no longer exists).

## Verification

- `pdm run pytest` — full suite passes, including the rewritten `test_story_header.py`, the updated `test_column.py` and `test_main_window.py`, and every other existing GUI test unaffected by this change (chat panel, rendering column, story detail/characters/locations/scenes widgets).
- `pdm run lint` — clean.
- Manually launch `pdm run scene-writer` and confirm: the sidebar pane and its collapse button are gone; the header shows "No story selected" plus New Story/Open buttons; New Story creates and selects a story, updating the header label; Open launches the modal, defaulting to non-archived stories, with the archived checkbox toggling an archived story's visibility in the list, Ok disabled with nothing selected, and OK/Cancel behaving as expected; the entity column shows Story/Characters/Locations/Scenes tabs in that order, each editable exactly as before; chat-driven story creation/edits still keep the header label and entity column in sync.

## Log

### Review - 2026-08-21T05:24:22Z - John Hoff

Reviewed e006-story-header-and-tabbed-entity-column against the two applicable lore items (linting, unit-testing). Both are explicitly honored: the Plan's Verification step runs `pdm run lint` clean and a full `pdm run pytest` pass, and the enumerated test-file changes (new `test_story_header.py` replacing `test_sidebar.py`, updates to `test_column.py` and `test_main_window.py`) correctly mirror the `src/scene/gui` module paths being added, replaced, or modified, with specific coverage called out for each new/changed behavior rather than a vague testing gesture. No conflicts with either lore item were found, and no unverifiable concerns were flagged given the narrow lore set in scope. Approved.

### Message - 2026-08-21T18:33:02Z - John Hoff

Manual testing turned up three UX refinements beyond the original Plan, applied during this encounter's execution: (1) double-clicking a row in StoryPickerDialog's list now accepts the dialog immediately (equivalent to selecting the row and clicking OK), rather than requiring an explicit OK click; (2) StoryHeader's "New"/"Open" buttons are left-justified next to the story label (immediately following it) instead of being pushed to the right edge of the header row; (3) the "New Story" button is relabeled "New" for brevity. None of these change the underlying data flow, signals, or the Requirements/Rationale/Plan's intent — purely presentation/interaction polish on the same StoryHeader/StoryPickerDialog built per the Plan.

### Completed - 2026-08-21T18:36:23Z - John Hoff

Verification passed: pdm run lint clean, full pdm run pytest suite green (364 tests), and pdm run scene-writer launches and behaves correctly — sidebar/collapse removed, StoryHeader (label + left-justified New/Open buttons) replaces it, Open's modal picker supports archived-inclusion toggling and double-click-to-open, and the entity column shows Story/Characters/Locations/Scenes tabs in order. README updated to match.
