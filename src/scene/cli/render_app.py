from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Markdown, Static

from scene.agent.config import LLMConfig
from scene.agent.rendering import (
    RenderComplete,
    RenderContentDelta,
    RenderReasoningDelta,
    build_render_messages,
    find_next_unrendered_scene,
    stream_render,
)
from scene.core.rendering import create_rendering, list_renderings, set_active_rendering
from scene.core.scene import list_scenes
from scene.core.scene_character import list_characters_for_scene
from scene.core.scene_location import list_locations_for_scene
from scene.core.story import list_stories
from scene.data.database import session_scope

NO_STORIES_TEXT = "No stories yet.\n\nCreate one with the coordinator chat."
NO_SCENES_TEXT = "This story has no scenes yet.\n\nAdd scenes with the coordinator chat."
ALL_RENDERED_TEXT = "All scenes are already rendered."


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
        f"Description:\n{scene.description}",
        "",
        f"Required actions: {scene.required_actions or '(none)'}",
        f"Length: {scene.length or '(unspecified)'}",
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
    """

    def __init__(self, story_id: int) -> None:
        super().__init__()
        self.story_id = story_id
        self.selected_scene_id: int | None = None
        self._output_text = ""

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="scene-column"):
                yield ListView(id="scene-list")
                yield Static("", id="scene-detail")
                yield Button("Render next scene", id="render-next")
            with Vertical(id="output-column"):
                yield VerticalScroll(id="output-scroll")

    async def on_mount(self) -> None:
        await self._refresh_scenes()

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
                return
        self.query_one("#scene-detail", Static).update(NO_SCENES_TEXT)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if not isinstance(item, SceneListItem):
            return
        self.selected_scene_id = item.scene_id
        with session_scope() as session:
            scene = next((scene for scene in list_scenes(session, self.story_id) if scene.id == item.scene_id), None)
            if scene is not None:
                self.query_one("#scene-detail", Static).update(_scene_detail_text(session, scene))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "render-next":
            return
        with session_scope() as session:
            scene = find_next_unrendered_scene(session, self.story_id)
        if scene is None:
            self._show_static_output(ALL_RENDERED_TEXT)
            return
        self._render_scene(scene.id)

    def _show_static_output(self, text: str) -> None:
        scroll = self.query_one("#output-scroll", VerticalScroll)
        scroll.remove_children()
        scroll.mount(Static(text, id="output-notice"))

    def _start_output(self) -> None:
        self._output_text = ""
        scroll = self.query_one("#output-scroll", VerticalScroll)
        scroll.remove_children()
        scroll.mount(Markdown("", id="output-text"))

    def _append_output(self, text: str) -> None:
        self._output_text += text
        self.query_one("#output-text", Markdown).update(self._output_text)
        self.query_one("#output-scroll", VerticalScroll).scroll_end(animate=False)

    @work(thread=True)
    def _render_scene(self, scene_id: int) -> None:
        with session_scope() as session:
            messages = build_render_messages(session, self.story_id, scene_id)

        self.app.call_from_thread(self._start_output)

        assembled = ""
        for event in stream_render(self.app.config, messages):
            if isinstance(event, (RenderReasoningDelta, RenderContentDelta)):
                self.app.call_from_thread(self._append_output, event.text)
            elif isinstance(event, RenderComplete):
                assembled = event.text

        with session_scope() as session:
            rendering = create_rendering(session, scene_id=scene_id, body=assembled)
            set_active_rendering(session, rendering.id)

        self.app.call_from_thread(self._refresh_scenes)


class RenderApp(App[None]):
    def __init__(self, config: LLMConfig) -> None:
        super().__init__()
        self.config = config

    def on_mount(self) -> None:
        self.push_screen(StoryPickerScreen())
