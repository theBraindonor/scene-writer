from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static
from textual.worker import Worker, WorkerState, get_current_worker

from scene.agent.config import LLMConfig
from scene.agent.continuity import accept_scene, regenerate_snapshots_from
from scene.agent.rendering import (
    RenderContentDelta,
    RenderReasoningDelta,
    build_render_messages,
    find_next_unrendered_scene,
    stream_render,
)
from scene.core.continuity_snapshot import get_snapshot
from scene.core.rendering import (
    create_rendering,
    delete_rendering,
    get_rendering,
    list_renderings,
    set_active_rendering,
)
from scene.core.scene import get_scene, list_scenes
from scene.core.scene_character import list_characters_for_scene
from scene.core.scene_location import list_locations_for_scene
from scene.core.story import list_stories
from scene.data.database import session_scope

NO_STORIES_TEXT = "No stories yet.\n\nCreate one with the coordinator chat."
NO_SCENES_TEXT = "This story has no scenes yet.\n\nAdd scenes with the coordinator chat."
ALL_RENDERED_TEXT = "All scenes are already rendered."
NO_RENDERINGS_TEXT = "This scene has no renderings yet."
DELETE_SOLE_RENDERING_TEXT = "Cannot delete a scene's only rendering."
DELETE_ACTIVE_RENDERING_TEXT = "Cannot delete the active rendering. Activate a different version first."
CANCEL_CONFIRM_TEXT = "Cancel generation? Y to confirm, N to keep writing."
CANCELLED_SAVED_TEXT = "Generation cancelled. Partial rendering saved."
CANCELLED_EMPTY_TEXT = "Generation cancelled. Nothing had been generated yet."
CONTINUITY_UPDATE_FAILED_TEXT = "Continuity snapshot update failed: {error}"
CONTINUITY_REGENERATE_FAILED_TEXT = "Continuity snapshot regeneration failed: {error}"
NO_CONTINUITY_SNAPSHOT_TEXT = "(No continuity snapshot yet.)"


def _has_active_rendering(session, scene_id: int) -> bool:
    return any(rendering.is_active for rendering in list_renderings(session, scene_id))


def _scene_status_label(session, scene) -> str:
    status = "✓" if _has_active_rendering(session, scene.id) else "○"
    heading = scene.heading or "(untitled)"
    return f"{status} {scene.position}. {heading}"


def _scene_detail_text(session, scene) -> str:
    lines = [
        f"Scene {scene.position}: {scene.heading or '(untitled)'}",
        "",
        f"Brief:\n{scene.brief}",
        "",
        f"Required actions: {scene.required_actions or '(none)'}",
        f"Desired outcome: {scene.desired_outcome or '(none)'}",
        f"Length: {scene.target_length or '(unspecified)'}",
        "",
        "Characters:",
    ]
    characters = list_characters_for_scene(session, scene.id)
    if characters:
        lines.extend(f"  {character.name}" for character in characters)
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append("Locations:")
    locations = list_locations_for_scene(session, scene.id)
    if locations:
        lines.extend(f"  {location.name}" for location in locations)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


class StoryListItem(ListItem):
    def __init__(self, story_id: int, label: str) -> None:
        super().__init__(Label(label), id=f"story-{story_id}")
        self.story_id = story_id


class SceneListItem(ListItem):
    def __init__(self, scene_id: int, label: str) -> None:
        super().__init__(Label(label))
        self.scene_id = scene_id


class VersionListItem(ListItem):
    def __init__(self, rendering_id: int, index: int, is_active: bool) -> None:
        marker = "●" if is_active else "○"
        suffix = " (active)" if is_active else ""
        super().__init__(Label(f"{marker} v{index}{suffix}"), id=f"version-{rendering_id}")
        self.rendering_id = rendering_id
        self.is_active = is_active


class StoryPickerScreen(Screen[None]):
    def compose(self) -> ComposeResult:
        yield Static("Select a story to render", id="picker-title")
        yield ListView(id="story-list")

    def on_mount(self) -> None:
        with session_scope() as session:
            stories = list_stories(session)
        list_view = self.query_one("#story-list", ListView)
        if not stories:
            list_view.display = False
            self.mount(Static(NO_STORIES_TEXT, id="no-stories"))
            return
        for story in stories:
            list_view.append(StoryListItem(story.id, f"{story.id}: {story.title}"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, StoryListItem):
            self.app.push_screen(RenderScreen(item.story_id))


class RenderScreen(Screen[None]):
    CSS = """
    Horizontal {
        height: 1fr;
    }

    #scene-column {
        width: 1fr;
        height: 1fr;
    }

    #output-column {
        width: 1fr;
        height: 1fr;
        border-left: solid $panel;
        padding: 1;
    }

    #scene-list {
        height: 1fr;
    }

    #scene-detail {
        height: auto;
        border-top: solid $panel;
        padding: 1;
    }

    #continuity-snapshot-text {
        height: auto;
        border-top: solid $panel;
        padding: 1;
    }

    #version-list {
        height: 6;
        border-top: solid $panel;
    }

    #version-text {
        height: auto;
        border-top: solid $panel;
        padding: 1;
    }

    #version-notice {
        height: auto;
        padding: 0 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel_generation", "Cancel generation", show=False),
        Binding("y", "confirm_cancel", "Confirm cancel", show=False),
        Binding("n", "dismiss_cancel", "Keep writing", show=False),
    ]

    def __init__(self, story_id: int) -> None:
        super().__init__()
        self.story_id = story_id
        self.selected_scene_id: int | None = None
        self.selected_rendering_id: int | None = None
        self._output_text = ""
        self._active_worker: Worker | None = None
        self._confirming_cancel = False

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="scene-column"):
                yield ListView(id="scene-list")
                yield Static("", id="scene-detail")
                with Horizontal(id="scene-actions"):
                    yield Button("Render next scene", id="render-next")
                    yield Button("Regenerate this scene", id="regenerate")
            with Vertical(id="output-column"):
                yield Static("", id="cancel-notice")
                yield Static("", id="continuity-notice")
                yield VerticalScroll(id="output-scroll")
                yield Static("Continuity Snapshot:", id="continuity-snapshot-label")
                yield Static("", id="continuity-snapshot-text")
                yield Static("Versions:", id="version-label")
                yield ListView(id="version-list")
                yield Static("", id="version-text")
                with Horizontal(id="version-actions"):
                    yield Button("Activate version", id="activate-version")
                    yield Button("Delete version", id="delete-version")
                yield Static("", id="version-notice")

    async def on_mount(self) -> None:
        await self._refresh_scenes()
        await self._refresh_versions()

    def action_cancel_generation(self) -> None:
        if self._active_worker is None or self._confirming_cancel:
            return
        self._confirming_cancel = True
        self.query_one("#cancel-notice", Static).update(CANCEL_CONFIRM_TEXT)

    def action_confirm_cancel(self) -> None:
        if not self._confirming_cancel:
            return
        self._confirming_cancel = False
        if self._active_worker is not None:
            self._active_worker.cancel()

    def action_dismiss_cancel(self) -> None:
        if not self._confirming_cancel:
            return
        self._confirming_cancel = False
        self.query_one("#cancel-notice", Static).update("")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker is not self._active_worker:
            return
        if event.state in (WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED):
            self._active_worker = None
            self._confirming_cancel = False

    async def _refresh_scenes(self) -> None:
        list_view = self.query_one("#scene-list", ListView)
        await list_view.clear()
        with session_scope() as session:
            scenes = list_scenes(session, self.story_id)
            for scene in scenes:
                list_view.append(SceneListItem(scene.id, _scene_status_label(session, scene)))

            if self.selected_scene_id is None and scenes:
                self.selected_scene_id = scenes[0].id

            selected = next((scene for scene in scenes if scene.id == self.selected_scene_id), None)
            if selected is not None:
                self.query_one("#scene-detail", Static).update(_scene_detail_text(session, selected))
                self._refresh_continuity_snapshot()
                return
        self.query_one("#scene-detail", Static).update(NO_SCENES_TEXT)
        self._refresh_continuity_snapshot()

    def _refresh_continuity_snapshot(self) -> None:
        text_widget = self.query_one("#continuity-snapshot-text", Static)
        if self.selected_scene_id is None:
            text_widget.update("")
            return
        with session_scope() as session:
            snapshot = get_snapshot(session, self.story_id, self.selected_scene_id)
        text_widget.update(snapshot.narrative_state if snapshot is not None else NO_CONTINUITY_SNAPSHOT_TEXT)

    async def _refresh_versions(self) -> None:
        version_list = self.query_one("#version-list", ListView)
        await version_list.clear()
        self.selected_rendering_id = None
        self.query_one("#version-text", Static).update("")
        self.query_one("#version-notice", Static).update("")
        if self.selected_scene_id is None:
            return
        with session_scope() as session:
            renderings = list_renderings(session, self.selected_scene_id)
        if not renderings:
            self.query_one("#version-text", Static).update(NO_RENDERINGS_TEXT)
            return
        for index, rendering in enumerate(renderings, start=1):
            version_list.append(VersionListItem(rendering.id, index, bool(rendering.is_active)))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, SceneListItem):
            self.selected_scene_id = item.scene_id
            with session_scope() as session:
                scene = next(
                    (scene for scene in list_scenes(session, self.story_id) if scene.id == item.scene_id), None
                )
                if scene is not None:
                    self.query_one("#scene-detail", Static).update(_scene_detail_text(session, scene))
            self._refresh_continuity_snapshot()
            self.run_worker(self._refresh_versions())
        elif isinstance(item, VersionListItem):
            self.selected_rendering_id = item.rendering_id
            with session_scope() as session:
                rendering = get_rendering(session, item.rendering_id)
            if rendering is not None:
                self.query_one("#version-text", Static).update(rendering.body)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "render-next":
            with session_scope() as session:
                scene = find_next_unrendered_scene(session, self.story_id)
            if scene is None:
                self._show_static_output(ALL_RENDERED_TEXT)
                return
            self._active_worker = self._render_scene(scene.id)
        elif button_id == "regenerate":
            if self.selected_scene_id is not None:
                self._active_worker = self._render_scene(self.selected_scene_id)
        elif button_id == "activate-version":
            self.run_worker(self._activate_selected_version())
        elif button_id == "delete-version":
            self.run_worker(self._delete_selected_version())

    async def _activate_selected_version(self) -> None:
        if self.selected_rendering_id is None:
            return
        with session_scope() as session:
            set_active_rendering(session, self.selected_rendering_id)
            scene = get_scene(session, self.selected_scene_id) if self.selected_scene_id is not None else None
            position = scene.position if scene is not None else None
        await self._refresh_versions()
        await self._refresh_scenes()
        if position is not None and self.app.continuity_config is not None:
            self._regenerate_snapshots(position)

    @work(thread=True)
    def _regenerate_snapshots(self, from_position: int) -> None:
        try:
            with session_scope() as session:
                regenerate_snapshots_from(self.app.continuity_config, session, self.story_id, from_position)
        except Exception as error:  # noqa: BLE001 - surfaced to the UI, never swallowed
            self.app.call_from_thread(
                self._show_continuity_notice, CONTINUITY_REGENERATE_FAILED_TEXT.format(error=error)
            )
        finally:
            self.app.call_from_thread(self._refresh_continuity_snapshot)

    async def _delete_selected_version(self) -> None:
        if self.selected_scene_id is None or self.selected_rendering_id is None:
            return
        with session_scope() as session:
            renderings = list_renderings(session, self.selected_scene_id)
            target = next((rendering for rendering in renderings if rendering.id == self.selected_rendering_id), None)
            if target is None:
                return
            if len(renderings) == 1:
                self.query_one("#version-notice", Static).update(DELETE_SOLE_RENDERING_TEXT)
                return
            if target.is_active:
                self.query_one("#version-notice", Static).update(DELETE_ACTIVE_RENDERING_TEXT)
                return
            delete_rendering(session, target.id)
        await self._refresh_versions()
        await self._refresh_scenes()

    def _show_static_output(self, text: str) -> None:
        scroll = self.query_one("#output-scroll", VerticalScroll)
        scroll.remove_children()
        scroll.mount(Static(text, id="output-notice"))

    def _start_output(self) -> None:
        self._output_text = ""
        self.query_one("#cancel-notice", Static).update("")
        scroll = self.query_one("#output-scroll", VerticalScroll)
        scroll.remove_children()
        # Plain Static, not Markdown: re-parsing the whole accumulated text as Markdown on
        # every streamed chunk causes partial tokens (a lone "*", "1." at a line start, etc.)
        # to be reinterpreted differently as more text arrives, making the pane visibly
        # reflow/jump mid-stream. Scene prose isn't meant to be structured Markdown anyway --
        # #version-text already displays a saved rendering's body as plain text, so this keeps
        # the live stream consistent with that.
        scroll.mount(Static("", id="output-text"))

    def _append_output(self, text: str) -> None:
        self._output_text += text
        self.query_one("#output-text", Static).update(self._output_text)
        self.query_one("#output-scroll", VerticalScroll).scroll_end(animate=False)

    def _show_cancelled_notice(self, saved: bool) -> None:
        self.query_one("#cancel-notice", Static).update(CANCELLED_SAVED_TEXT if saved else CANCELLED_EMPTY_TEXT)

    def _show_continuity_notice(self, text: str) -> None:
        self.query_one("#continuity-notice", Static).update(text)

    @work(thread=True)
    def _render_scene(self, scene_id: int) -> None:
        worker = get_current_worker()
        with session_scope() as session:
            messages = build_render_messages(session, self.story_id, scene_id)

        self.app.call_from_thread(self._start_output)

        content_parts: list[str] = []
        cancelled = False
        stream = stream_render(self.app.config, messages)
        while True:
            if worker.is_cancelled:
                cancelled = True
                break
            try:
                event = next(stream)
            except StopIteration:
                break
            if isinstance(event, RenderContentDelta):
                content_parts.append(event.text)
                self.app.call_from_thread(self._append_output, event.text)
            elif isinstance(event, RenderReasoningDelta):
                self.app.call_from_thread(self._append_output, event.text)

        assembled = "".join(content_parts)

        if assembled:
            with session_scope() as session:
                rendering = create_rendering(session, scene_id=scene_id, body=assembled)
                set_active_rendering(session, rendering.id)
                if self.app.continuity_config is not None:
                    try:
                        accept_scene(self.app.continuity_config, session, self.story_id, scene_id)
                    except Exception as error:  # noqa: BLE001 - surfaced to the UI, never swallowed
                        self.app.call_from_thread(
                            self._show_continuity_notice, CONTINUITY_UPDATE_FAILED_TEXT.format(error=error)
                        )

        self.app.call_from_thread(self._refresh_scenes)
        self.app.call_from_thread(self._refresh_versions)
        if cancelled:
            self.app.call_from_thread(self._show_cancelled_notice, bool(assembled))


class RenderApp(App[None]):
    def __init__(self, config: LLMConfig, continuity_config: LLMConfig | None = None) -> None:
        super().__init__()
        self.config = config
        self.continuity_config = continuity_config

    def on_mount(self) -> None:
        self.push_screen(StoryPickerScreen())
