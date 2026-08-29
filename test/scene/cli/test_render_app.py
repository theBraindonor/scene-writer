import asyncio
import threading
import time
from dataclasses import dataclass, field

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Static

import scene.agent.rendering as rendering_module
import scene.cli.render_app as render_app_module
import scene.data.database as database_module
from scene.agent.config import LLMConfig
from scene.cli.render_app import (
    ALL_RENDERED_TEXT,
    CANCEL_CONFIRM_TEXT,
    CANCELLED_SAVED_TEXT,
    DELETE_ACTIVE_RENDERING_TEXT,
    DELETE_SOLE_RENDERING_TEXT,
    NO_CONTINUITY_SNAPSHOT_TEXT,
    NO_SCENES_TEXT,
    RenderApp,
    RenderScreen,
    SceneListItem,
    StoryListItem,
    StoryPickerScreen,
    VersionListItem,
)
from scene.core.character import create_character
from scene.core.continuity_snapshot import create_snapshot, delete_snapshot
from scene.core.location import create_location
from scene.core.rendering import create_rendering, list_renderings, set_active_rendering
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


def gated_stream(monkeypatch, texts):
    """Streams one chunk per text, each held back until its gate Event is set.

    Lets a test deterministically control exactly how many chunks a background
    render worker has consumed before it inspects cancellation, without any
    wall-clock timing races.
    """
    gates = [threading.Event() for _ in texts]

    def fake_stream_complete(config, messages, tools=None):
        for gate, text in zip(gates, texts):
            gate.wait()
            yield make_chunk(content=text)

    monkeypatch.setattr(rendering_module, "stream_complete", fake_stream_complete)
    return gates


async def wait_until(predicate, timeout=2.0, interval=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(interval)
    raise AssertionError("condition not met within timeout")


def make_config():
    return LLMConfig(model="openai/test-model", api_base=None, api_key=None)


def seed_story_with_scene():
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A story brief")
        character = create_character(session, story_id=story.id, name="Alex")
        location = create_location(session, story_id=story.id, name="The Tavern")
        scene = create_scene(session, story_id=story.id, position=0, brief="Opening", heading="Arrival")
        assign_character(session, scene.id, character.id)
        assign_location(session, scene.id, location.id)
        return story.id, scene.id


async def test_story_picker_lists_stories_and_selecting_shows_scenes():
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A story brief")
        create_scene(session, story_id=story.id, position=0, brief="Opening", heading="Arrival")
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

        output = app.screen.query_one("#output-text", Static)
        assert output.content == "Once upon a time."

        with session_scope() as session:
            renderings = list_renderings(session, scene_id)
            active = [rendering for rendering in renderings if rendering.is_active]
            assert len(active) == 1
            assert active[0].body == "Once upon a time."
            assert active[0].body_reasoning is None


async def test_render_next_scene_persists_reasoning_when_present(monkeypatch):
    story_id, scene_id = seed_story_with_scene()
    script_stream(
        monkeypatch,
        [make_chunk(reasoning_content="Thinking it through."), make_chunk(content="Once upon a time.")],
    )

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click("#render-next")
        await app.workers.wait_for_complete()
        await pilot.pause()

        with session_scope() as session:
            renderings = list_renderings(session, scene_id)
            active = [rendering for rendering in renderings if rendering.is_active]
            assert active[0].body_reasoning == "Thinking it through."


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
        story = create_story(session, title="A Story", story_brief="A story brief")
        create_scene(session, story_id=story.id, position=0, brief="First", heading="Arrival")
        create_scene(session, story_id=story.id, position=1, brief="Second", heading="Departure")
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
        story = create_story(session, title="Empty Story", story_brief="A story brief")
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


async def test_regenerate_creates_new_version_and_keeps_previous(monkeypatch):
    story_id, scene_id = seed_story_with_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        first_id = first.id

    script_stream(monkeypatch, [make_chunk(content="Second version.")])

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click("#regenerate")
        await app.workers.wait_for_complete()
        await pilot.pause()

        output = app.screen.query_one("#output-text", Static)
        assert output.content == "Second version."

        with session_scope() as session:
            renderings = list_renderings(session, scene_id)
            assert len(renderings) == 2
            assert renderings[0].id == first_id
            assert renderings[0].body == "First version."
            active = [rendering for rendering in renderings if rendering.is_active]
            assert len(active) == 1
            assert active[0].body == "Second version."


async def test_activating_version_updates_active_indicator_and_scene_status():
    story_id, scene_id = seed_story_with_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        second = create_rendering(session, scene_id=scene_id, body="Second version.")
        set_active_rendering(session, second.id)
        first_id = first.id

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        items = list(app.screen.query(VersionListItem))
        assert len(items) == 2
        assert not app.screen.query_one(f"#version-{first_id}", VersionListItem).is_active

        await pilot.click(f"#version-{first_id}")
        await pilot.pause()
        assert app.screen.selected_rendering_id == first_id

        await pilot.click("#activate-version")
        await app.workers.wait_for_complete()
        await pilot.pause()

        with session_scope() as session:
            renderings = list_renderings(session, scene_id)
            active = [rendering for rendering in renderings if rendering.is_active]
            assert len(active) == 1
            assert active[0].id == first_id

        assert app.screen.query_one(f"#version-{first_id}", VersionListItem).is_active
        scene_item = app.screen.query_one(SceneListItem)
        assert "✓" in str(scene_item.query_one("Label").content)


async def test_render_next_scene_calls_accept_scene_when_continuity_config_set(monkeypatch):
    story_id, scene_id = seed_story_with_scene()
    script_stream(monkeypatch, [make_chunk(content="Once upon a time.")])

    captured = {}

    def fake_accept_scene(config, session, story_id_arg, scene_id_arg):
        captured["config"] = config
        captured["story_id"] = story_id_arg
        captured["scene_id"] = scene_id_arg

    monkeypatch.setattr(render_app_module, "accept_scene", fake_accept_scene)

    continuity_config = make_config()
    app = RenderApp(make_config(), continuity_config)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click("#render-next")
        await app.workers.wait_for_complete()
        await pilot.pause()

    assert captured["config"] is continuity_config
    assert captured["story_id"] == story_id
    assert captured["scene_id"] == scene_id


async def test_render_next_scene_skips_accept_scene_without_continuity_config(monkeypatch):
    story_id, _scene_id = seed_story_with_scene()
    script_stream(monkeypatch, [make_chunk(content="Once upon a time.")])

    def unexpected_accept_scene(config, session, story_id_arg, scene_id_arg):
        raise AssertionError("accept_scene() should not be called without a continuity_config")

    monkeypatch.setattr(render_app_module, "accept_scene", unexpected_accept_scene)

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click("#render-next")
        await app.workers.wait_for_complete()
        await pilot.pause()


async def test_render_next_scene_shows_notice_when_accept_scene_fails(monkeypatch):
    story_id, _scene_id = seed_story_with_scene()
    script_stream(monkeypatch, [make_chunk(content="Once upon a time.")])

    def failing_accept_scene(config, session, story_id_arg, scene_id_arg):
        raise RuntimeError("boom")

    monkeypatch.setattr(render_app_module, "accept_scene", failing_accept_scene)

    app = RenderApp(make_config(), make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click("#render-next")
        await app.workers.wait_for_complete()
        await pilot.pause()

        notice = app.screen.query_one("#continuity-notice", Static)
        assert "boom" in str(notice.content)


async def test_activating_version_calls_regenerate_snapshots_from_when_continuity_config_set(monkeypatch):
    story_id, scene_id = seed_story_with_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        second = create_rendering(session, scene_id=scene_id, body="Second version.")
        set_active_rendering(session, second.id)
        first_id = first.id

    captured = {}

    def fake_regenerate(config, session, story_id_arg, from_position):
        captured["config"] = config
        captured["story_id"] = story_id_arg
        captured["from_position"] = from_position

    monkeypatch.setattr(render_app_module, "regenerate_snapshots_from", fake_regenerate)

    continuity_config = make_config()
    app = RenderApp(make_config(), continuity_config)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click(f"#version-{first_id}")
        await pilot.pause()

        await pilot.click("#activate-version")
        await app.workers.wait_for_complete()
        await pilot.pause()

    assert captured["config"] is continuity_config
    assert captured["story_id"] == story_id
    assert captured["from_position"] == 0


async def test_activating_version_shows_notice_when_regenerate_fails(monkeypatch):
    story_id, scene_id = seed_story_with_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        second = create_rendering(session, scene_id=scene_id, body="Second version.")
        set_active_rendering(session, second.id)
        first_id = first.id

    def failing_regenerate(config, session, story_id_arg, from_position):
        raise RuntimeError("boom")

    monkeypatch.setattr(render_app_module, "regenerate_snapshots_from", failing_regenerate)

    app = RenderApp(make_config(), make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click(f"#version-{first_id}")
        await pilot.pause()

        await pilot.click("#activate-version")
        await app.workers.wait_for_complete()
        await pilot.pause()

        notice = app.screen.query_one("#continuity-notice", Static)
        assert "boom" in str(notice.content)


async def test_continuity_snapshot_panel_shows_placeholder_when_none_exists():
    story_id, _scene_id = seed_story_with_scene()

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        panel = app.screen.query_one("#continuity-snapshot-text", Static)
        assert str(panel.content) == NO_CONTINUITY_SNAPSHOT_TEXT


async def test_continuity_snapshot_panel_shows_saved_snapshot():
    story_id, scene_id = seed_story_with_scene()
    with session_scope() as session:
        create_snapshot(session, story_id, scene_id, "Mara is at the station.")

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        panel = app.screen.query_one("#continuity-snapshot-text", Static)
        assert str(panel.content) == "Mara is at the station."


async def test_continuity_snapshot_panel_updates_after_generation(monkeypatch):
    story_id, _scene_id = seed_story_with_scene()
    script_stream(monkeypatch, [make_chunk(content="Once upon a time.")])

    def fake_accept_scene(config, session, story_id_arg, scene_id_arg):
        create_snapshot(session, story_id_arg, scene_id_arg, "Fresh state.")

    monkeypatch.setattr(render_app_module, "accept_scene", fake_accept_scene)

    app = RenderApp(make_config(), make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click("#render-next")
        await app.workers.wait_for_complete()
        await pilot.pause()

        panel = app.screen.query_one("#continuity-snapshot-text", Static)
        assert str(panel.content) == "Fresh state."


async def test_continuity_snapshot_panel_updates_after_activating_version(monkeypatch):
    story_id, scene_id = seed_story_with_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        second = create_rendering(session, scene_id=scene_id, body="Second version.")
        set_active_rendering(session, second.id)
        first_id = first.id
        create_snapshot(session, story_id, scene_id, "Stale state.")

    def fake_regenerate(config, session, story_id_arg, from_position):
        delete_snapshot(session, story_id_arg, scene_id)
        create_snapshot(session, story_id_arg, scene_id, "Fresh state.")

    monkeypatch.setattr(render_app_module, "regenerate_snapshots_from", fake_regenerate)

    app = RenderApp(make_config(), make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click(f"#version-{first_id}")
        await pilot.pause()

        await pilot.click("#activate-version")
        await app.workers.wait_for_complete()
        await pilot.pause()

        panel = app.screen.query_one("#continuity-snapshot-text", Static)
        assert str(panel.content) == "Fresh state."


async def test_delete_refuses_scene_sole_rendering():
    story_id, scene_id = seed_story_with_scene()
    with session_scope() as session:
        only = create_rendering(session, scene_id=scene_id, body="Only version.")
        set_active_rendering(session, only.id)
        only_id = only.id

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click(f"#version-{only_id}")
        await pilot.pause()

        await pilot.click("#delete-version")
        await app.workers.wait_for_complete()
        await pilot.pause()

        notice = app.screen.query_one("#version-notice", Static)
        assert str(notice.content) == DELETE_SOLE_RENDERING_TEXT

        with session_scope() as session:
            assert len(list_renderings(session, scene_id)) == 1


async def test_delete_refuses_currently_active_rendering():
    story_id, scene_id = seed_story_with_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        second = create_rendering(session, scene_id=scene_id, body="Second version.")
        set_active_rendering(session, second.id)
        second_id = second.id

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click(f"#version-{second_id}")
        await pilot.pause()

        await pilot.click("#delete-version")
        await app.workers.wait_for_complete()
        await pilot.pause()

        notice = app.screen.query_one("#version-notice", Static)
        assert str(notice.content) == DELETE_ACTIVE_RENDERING_TEXT

        with session_scope() as session:
            renderings = list_renderings(session, scene_id)
            assert len(renderings) == 2
            active = [rendering for rendering in renderings if rendering.is_active]
            assert len(active) == 1
            assert active[0].id == second_id


async def test_delete_removes_inactive_version():
    story_id, scene_id = seed_story_with_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)
        second = create_rendering(session, scene_id=scene_id, body="Second version.")
        set_active_rendering(session, second.id)
        first_id = first.id
        second_id = second.id

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click(f"#version-{first_id}")
        await pilot.pause()

        await pilot.click("#delete-version")
        await app.workers.wait_for_complete()
        await pilot.pause()

        notice = app.screen.query_one("#version-notice", Static)
        assert str(notice.content) == ""

        with session_scope() as session:
            renderings = list_renderings(session, scene_id)
            assert len(renderings) == 1
            assert renderings[0].id == second_id
            assert renderings[0].is_active

        items = list(app.screen.query(VersionListItem))
        assert len(items) == 1
        assert items[0].rendering_id == second_id


async def test_escape_then_y_cancels_generation_and_saves_partial_content(monkeypatch):
    story_id, scene_id = seed_story_with_scene()
    gates = gated_stream(monkeypatch, ["word0 ", "word1 ", "word2 "])

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click("#render-next")
        gates[0].set()
        await wait_until(lambda: "word0 " in app.screen.query_one("#output-text", Static).content)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()
        assert str(app.screen.query_one("#cancel-notice", Static).content) == CANCEL_CONFIRM_TEXT

        await pilot.press("y")
        gates[1].set()
        # A cancelled thread worker's wrapping Task resolves as soon as .cancel() is
        # called, well before the real OS thread finishes its cleanup — so poll for
        # the thread's own final signal instead of trusting workers.wait_for_complete().
        await wait_until(lambda: str(app.screen.query_one("#cancel-notice", Static).content) == CANCELLED_SAVED_TEXT)
        await pilot.pause()

        output = app.screen.query_one("#output-text", Static)
        assert output.content == "word0 word1 "

        with session_scope() as session:
            renderings = list_renderings(session, scene_id)
            assert len(renderings) == 1
            assert renderings[0].is_active
            assert renderings[0].body == "word0 word1 "


async def test_escape_then_n_keeps_generation_running_to_completion(monkeypatch):
    story_id, scene_id = seed_story_with_scene()
    gates = gated_stream(monkeypatch, ["word0 ", "word1 ", "word2 ", "word3 "])
    full_text = "word0 word1 word2 word3 "

    app = RenderApp(make_config())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click(f"#story-{story_id}")
        await pilot.pause()

        await pilot.click("#render-next")
        gates[0].set()
        await wait_until(lambda: "word0 " in app.screen.query_one("#output-text", Static).content)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()
        assert str(app.screen.query_one("#cancel-notice", Static).content) == CANCEL_CONFIRM_TEXT

        await pilot.press("n")
        await pilot.pause()
        assert str(app.screen.query_one("#cancel-notice", Static).content) == ""

        for gate in gates[1:]:
            gate.set()
        await app.workers.wait_for_complete()
        await pilot.pause()

        output = app.screen.query_one("#output-text", Static)
        assert output.content == full_text

        with session_scope() as session:
            renderings = list_renderings(session, scene_id)
            assert len(renderings) == 1
            assert renderings[0].body == full_text


def test_action_cancel_generation_noop_without_active_worker():
    screen = RenderScreen(story_id=1)
    screen.action_cancel_generation()
    assert screen._confirming_cancel is False


def test_action_confirm_and_dismiss_cancel_noop_when_not_confirming():
    screen = RenderScreen(story_id=1)
    screen.action_confirm_cancel()
    screen.action_dismiss_cancel()
    assert screen._confirming_cancel is False
