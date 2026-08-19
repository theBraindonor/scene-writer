from dataclasses import dataclass, field

import pytest

import scene.agent.rendering as rendering_module
from scene.agent.config import LLMConfig
from scene.agent.rendering import (
    RenderComplete,
    RenderContentDelta,
    RenderReasoningDelta,
    build_render_messages,
    find_next_unrendered_scene,
    stream_render,
)
from scene.core.character import create_character
from scene.core.location import create_location
from scene.core.rendering import create_rendering, set_active_rendering
from scene.core.scene import create_scene
from scene.core.scene_character import assign_character
from scene.core.scene_location import assign_location
from scene.core.story import create_story
from scene.data.database import get_engine, get_session_factory, init_db


@pytest.fixture
def session():
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    try:
        with get_session_factory(engine)() as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def story_id(session):
    story = create_story(session, title="Title", scenario="A grand scenario", style_guidance="Terse, present tense")
    return story.id


def _activate(session, scene_id, body):
    rendering = create_rendering(session, scene_id=scene_id, body=body)
    set_active_rendering(session, rendering.id)
    return rendering


def test_find_next_unrendered_scene_returns_none_when_no_scenes(session, story_id):
    assert find_next_unrendered_scene(session, story_id) is None


def test_find_next_unrendered_scene_returns_lowest_position_without_active_rendering(session, story_id):
    first = create_scene(session, story_id=story_id, position=0, description="First")
    second = create_scene(session, story_id=story_id, position=1, description="Second")
    _activate(session, first.id, "First scene prose.")

    result = find_next_unrendered_scene(session, story_id)

    assert result.id == second.id


def test_find_next_unrendered_scene_returns_none_when_all_rendered(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, description="First")
    _activate(session, scene.id, "First scene prose.")

    assert find_next_unrendered_scene(session, story_id) is None


def test_build_render_messages_system_message_has_scenario_and_style_guidance(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, description="First")

    messages = build_render_messages(session, story_id, scene.id)

    assert messages[0]["role"] == "system"
    assert "A grand scenario" in messages[0]["content"]
    assert "Terse, present tense" in messages[0]["content"]


def test_build_render_messages_no_prior_scenes_has_single_user_message(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, description="First", heading="Arrival")

    messages = build_render_messages(session, story_id, scene.id)

    assert len(messages) == 2
    assert messages[1]["role"] == "user"
    assert "Arrival" in messages[1]["content"]
    assert "Write this scene's prose now." in messages[1]["content"]


def test_build_render_messages_includes_prior_scene_detail_and_active_rendering(session, story_id):
    first = create_scene(session, story_id=story_id, position=0, description="First", heading="Arrival")
    second = create_scene(session, story_id=story_id, position=1, description="Second", heading="Departure")
    _activate(session, first.id, "The prose of the first scene.")

    messages = build_render_messages(session, story_id, second.id)

    assert len(messages) == 4
    assert messages[1]["role"] == "user"
    assert "Arrival" in messages[1]["content"]
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "The prose of the first scene."
    assert messages[3]["role"] == "user"
    assert "Departure" in messages[3]["content"]


def test_build_render_messages_includes_character_and_location_detail(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, description="First")
    character = create_character(session, story_id=story_id, name="Alex", description="A wanderer", motive="Find home")
    location = create_location(session, story_id=story_id, name="The Tavern", description="A cozy inn")
    assign_character(session, scene.id, character.id)
    assign_location(session, scene.id, location.id)

    messages = build_render_messages(session, story_id, scene.id)

    content = messages[-1]["content"]
    assert "Alex" in content
    assert "Find home" in content
    assert "The Tavern" in content
    assert "A cozy inn" in content


def test_build_render_messages_raises_when_prior_scene_has_no_active_rendering(session, story_id):
    create_scene(session, story_id=story_id, position=0, description="First")
    second = create_scene(session, story_id=story_id, position=1, description="Second")

    with pytest.raises(ValueError, match="no active rendering"):
        build_render_messages(session, story_id, second.id)


def test_build_render_messages_raises_for_missing_story(session):
    with pytest.raises(ValueError, match="not found"):
        build_render_messages(session, 999, 1)


def test_build_render_messages_raises_for_missing_scene(session, story_id):
    with pytest.raises(ValueError, match="not found"):
        build_render_messages(session, story_id, 999)


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


def test_stream_render_yields_content_deltas_and_complete(monkeypatch):
    script_stream(monkeypatch, [make_chunk(content="Once "), make_chunk(content="upon a time.")])

    events = list(stream_render(make_config(), []))

    assert events == [
        RenderContentDelta("Once "),
        RenderContentDelta("upon a time."),
        RenderComplete("Once upon a time."),
    ]


def test_stream_render_yields_reasoning_deltas(monkeypatch):
    script_stream(monkeypatch, [make_chunk(reasoning_content="Thinking..."), make_chunk(content="The scene.")])

    events = list(stream_render(make_config(), []))

    assert events == [
        RenderReasoningDelta("Thinking..."),
        RenderContentDelta("The scene."),
        RenderComplete("The scene."),
    ]


def test_stream_render_empty_stream_yields_only_complete(monkeypatch):
    script_stream(monkeypatch, [])

    events = list(stream_render(make_config(), []))

    assert events == [RenderComplete("")]
