from dataclasses import dataclass, field

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Markdown, Static

import scene.agent.rendering as rendering_module
import scene.data.database as database_module
from scene.agent.config import LLMConfig
from scene.cli.render_app import (
    ALL_RENDERED_TEXT,
    NO_SCENES_TEXT,
    RenderApp,
    RenderScreen,
    StoryListItem,
    StoryPickerScreen,
)
from scene.core.character import create_character
from scene.core.location import create_location
from scene.core.rendering import list_renderings
from scene.core.scene import create_scene
from scene.core.scene_character import assign_character
from scene.core.scene_location import assign_location
from scene.core.story import create_story
from scene.data.database import session_scope


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


@dataclass
class FakeDelta:
    content: str | None = None
    reasoning_content: str | None = None


@dataclass
class FakeChoice:
    delta: FakeDelta


@dataclass
class FakeChunk:
    choices: list[FakeChoice] = field(default_factory=list)


def make_chunk(content=None, reasoning_content=None):
    return FakeChunk(choices=[FakeChoice(delta=FakeDelta(content=content, reasoning_content=reasoning_content))])


def script_stream(monkeypatch, chunks):
    def fake_stream_complete(config, messages, tools=None):
        return iter(chunks)

    monkeypatch.setattr(rendering_module, "stream_complete", fake_stream_complete)


def make_config():
    return LLMConfig(model="openai/test-model", api_base=None, api_key=None)


def seed_story_with_scene():
    with session_scope() as session:
        story = create_story(session, title="A Story", scenario="A scenario")
        character = create_character(session, story_id=story.id, name="Alex")
        location = create_location(session, story_id=story.id, name="The Tavern")
        scene = create_scene(session, story_id=story.id, position=0, description="Opening", heading="Arrival")
        assign_character(session, scene.id, character.id)
        assign_location(session, scene.id, location.id)
        return story.id, scene.id


async def test_story_picker_lists_stories_and_selecting_shows_scenes():
    with session_scope() as session:
        story = create_story(session, title="A Story", scenario="A scenario")
        create_scene(session, story_id=story.id, position=0, description="Opening", heading="Arrival")
        story_id = story.id

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()

        picker = app.screen
        assert isinstance(picker, StoryPickerScreen)
        items = list(picker.query(StoryListItem))
        assert len(items) == 1
        assert "A Story" in str(items[0].query_one("Label").content)

        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        assert isinstance(app.screen, RenderScreen)
        assert "Arrival" in str(app.screen.query_one("#scene-detail", Static).content)


async def test_story_picker_shows_placeholder_when_no_stories():
    app = RenderApp(make_config())
    async with app.run_test():
        picker = app.screen
        assert isinstance(picker, StoryPickerScreen)
        assert picker.query_one("#no-stories", Static)


async def test_render_next_scene_streams_and_persists_active_rendering(monkeypatch):
    story_id, scene_id = seed_story_with_scene()
    script_stream(monkeypatch, [make_chunk(content="Once "), make_chunk(content="upon a time.")])

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click("#render-next")
        await app.workers.wait_for_complete()
        await pilot.pause()

        output = app.screen.query_one("#output-text", Markdown)
        assert output.source == "Once upon a time."

        with session_scope() as session:
            renderings = list_renderings(session, scene_id)
            active = [rendering for rendering in renderings if rendering.is_active]
            assert len(active) == 1
            assert active[0].body == "Once upon a time."


async def test_output_pane_auto_scrolls_on_every_streamed_chunk(monkeypatch):
    story_id, _ = seed_story_with_scene()
    script_stream(monkeypatch, [make_chunk(content="a"), make_chunk(content="b"), make_chunk(content="c")])

    calls = []
    original_scroll_end = VerticalScroll.scroll_end

    def spy_scroll_end(self, *args, **kwargs):
        if self.id == "output-scroll":
            calls.append(1)
        return original_scroll_end(self, *args, **kwargs)

    monkeypatch.setattr(VerticalScroll, "scroll_end", spy_scroll_end)

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click("#render-next")
        await app.workers.wait_for_complete()
        await pilot.pause()

        # One scroll per streamed content chunk, not just once at the end.
        assert calls.count(1) >= 3


async def test_render_next_scene_shows_notice_when_all_scenes_rendered(monkeypatch):
    story_id, _ = seed_story_with_scene()
    script_stream(monkeypatch, [make_chunk(content="The scene.")])

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()
        await pilot.click("#render-next")
        await app.workers.wait_for_complete()
        await pilot.pause()

        def unexpected_stream_complete(config, messages, tools=None):
            raise AssertionError("stream_complete() should not be called when all scenes are rendered")

        monkeypatch.setattr(rendering_module, "stream_complete", unexpected_stream_complete)

        await pilot.click("#render-next")
        await pilot.pause()

        notice = app.screen.query_one("#output-notice", Static)
        assert str(notice.content) == ALL_RENDERED_TEXT


async def test_scene_list_highlight_updates_detail_pane():
    with session_scope() as session:
        story = create_story(session, title="A Story", scenario="A scenario")
        create_scene(session, story_id=story.id, position=0, description="First", heading="Arrival")
        create_scene(session, story_id=story.id, position=1, description="Second", heading="Departure")
        story_id = story.id

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click("#scene-list")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()

        assert "Departure" in str(app.screen.query_one("#scene-detail", Static).content)


async def test_render_screen_shows_no_scenes_placeholder_when_story_has_no_scenes():
    with session_scope() as session:
        story = create_story(session, title="Empty Story", scenario="A scenario")
        story_id = story.id

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        assert str(app.screen.query_one("#scene-detail", Static).content) == NO_SCENES_TEXT


def test_on_button_pressed_ignores_unrelated_buttons():
    class FakeButton:
        id = "not-render-next"

    class FakeEvent:
        button = FakeButton()

    screen = RenderScreen(story_id=1)
    screen.on_button_pressed(FakeEvent())


def test_on_list_view_highlighted_ignores_non_scene_items():
    class FakeEvent:
        item = None

    screen = RenderScreen(story_id=1)
    screen.on_list_view_highlighted(FakeEvent())
    assert screen.selected_scene_id is None
