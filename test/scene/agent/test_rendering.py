from dataclasses import dataclass, field

import pytest

import scene.agent.rendering as rendering_module
from scene.agent.config import LLMConfig
from scene.agent.rendering import (
    RenderComplete,
    RenderContentDelta,
    RenderReasoningDelta,
    build_render_messages,
    earlier_scenes_rendered,
    find_next_unrendered_scene,
    stream_render,
)
from scene.core.character import create_character
from scene.core.continuity_snapshot import create_snapshot
from scene.core.location import create_location
from scene.core.rendering import create_rendering, set_active_rendering
from scene.core.scene import create_scene
from scene.core.scene_character import assign_character
from scene.core.scene_location import assign_location
from scene.core.story import create_story, update_story
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
    story = create_story(
        session, title="Title", story_brief="A grand story brief", style_guidance="Terse, present tense"
    )
    return story.id


def _activate(session, scene_id, body):
    rendering = create_rendering(session, scene_id=scene_id, body=body)
    set_active_rendering(session, rendering.id)
    return rendering


def test_find_next_unrendered_scene_returns_none_when_no_scenes(session, story_id):
    assert find_next_unrendered_scene(session, story_id) is None


def test_find_next_unrendered_scene_returns_lowest_position_without_active_rendering(session, story_id):
    first = create_scene(session, story_id=story_id, position=0, brief="First")
    second = create_scene(session, story_id=story_id, position=1, brief="Second")
    _activate(session, first.id, "First scene prose.")

    result = find_next_unrendered_scene(session, story_id)

    assert result.id == second.id


def test_find_next_unrendered_scene_returns_none_when_all_rendered(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="First")
    _activate(session, scene.id, "First scene prose.")

    assert find_next_unrendered_scene(session, story_id) is None


def test_earlier_scenes_rendered_true_when_no_earlier_scenes(session, story_id):
    create_scene(session, story_id=story_id, position=0, brief="First")

    assert earlier_scenes_rendered(session, story_id, target_position=0) is True


def test_earlier_scenes_rendered_true_when_all_earlier_scenes_active(session, story_id):
    first = create_scene(session, story_id=story_id, position=0, brief="First")
    create_scene(session, story_id=story_id, position=1, brief="Second")
    _activate(session, first.id, "First scene prose.")

    assert earlier_scenes_rendered(session, story_id, target_position=1) is True


def test_earlier_scenes_rendered_false_when_an_earlier_scene_has_no_active_rendering(session, story_id):
    create_scene(session, story_id=story_id, position=0, brief="First")
    create_scene(session, story_id=story_id, position=1, brief="Second")

    assert earlier_scenes_rendered(session, story_id, target_position=1) is False


def test_build_render_messages_system_message_has_story_brief_and_style_guidance(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="First")

    messages = build_render_messages(session, story_id, scene.id)

    assert messages[0]["role"] == "system"
    assert "A grand story brief" in messages[0]["content"]
    assert "Terse, present tense" in messages[0]["content"]


def test_build_render_messages_system_message_has_requirements_before_story_brief(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="First")

    messages = build_render_messages(session, story_id, scene.id)

    system_content = messages[0]["content"]
    assert "## Requirements" in system_content
    assert "## Story Brief" in system_content
    assert system_content.index("## Requirements") < system_content.index("## Story Brief")
    assert "- Use the requested point of view and tense." in system_content


def test_build_render_messages_scene_brief_has_caption_and_final_instructions(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="First")

    messages = build_render_messages(session, story_id, scene.id)

    user_content = messages[1]["content"]
    assert "complementary" in user_content
    assert "## Final Instructions" in user_content
    assert "Above all else, satisfy this Scene Brief" in user_content
    assert "do not add a tidy conclusion" in user_content
    scene_brief_index = user_content.index("## Scene Brief")
    final_instructions_index = user_content.index("## Final Instructions")
    assert scene_brief_index < final_instructions_index


def test_build_render_messages_system_message_has_scene_generation_instructions_last(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="First")

    messages = build_render_messages(session, story_id, scene.id)

    system_content = messages[0]["content"]
    assert "## Scene Generation Instructions" in system_content
    assert "The next message contains this scene's brief" in system_content
    assert system_content.index("## Story Brief") < system_content.index("## Scene Generation Instructions")


def test_build_render_messages_no_prior_scenes_has_single_user_message(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="First", heading="Arrival")

    messages = build_render_messages(session, story_id, scene.id)

    assert len(messages) == 2
    assert messages[1]["role"] == "user"
    assert "Heading: Arrival" in messages[1]["content"]
    assert "## Current Canon" not in messages[1]["content"]
    assert "## Optional Recent Prose" not in messages[1]["content"]


def test_build_render_messages_includes_current_canon_and_recent_prose(session, story_id):
    first = create_scene(session, story_id=story_id, position=0, brief="First", heading="Arrival")
    second = create_scene(session, story_id=story_id, position=1, brief="Second", heading="Departure")
    _activate(session, first.id, "The prose of the first scene.")
    create_snapshot(session, story_id, first.id, "Mara is at the station.")

    messages = build_render_messages(session, story_id, second.id)

    assert len(messages) == 2
    user_content = messages[1]["content"]
    assert "## Current Canon\n\nMara is at the station." in user_content
    assert "## Optional Recent Prose\n\nThe prose of the first scene." in user_content
    assert "Heading: Departure" in user_content


def test_build_render_messages_omits_current_canon_and_recent_prose_when_absent(session, story_id):
    create_scene(session, story_id=story_id, position=0, brief="First")
    second = create_scene(session, story_id=story_id, position=1, brief="Second")

    messages = build_render_messages(session, story_id, second.id)

    user_content = messages[1]["content"]
    assert "## Current Canon" not in user_content
    assert "## Optional Recent Prose" not in user_content


def test_build_render_messages_scene_brief_sections_appear_in_requested_order(session, story_id):
    character = create_character(session, story_id=story_id, name="Mara")
    scene = create_scene(
        session,
        story_id=story_id,
        position=0,
        brief="First",
        heading="Arrival",
        pov_character_id=character.id,
        required_actions="Knock on the door",
        desired_outcome="Mara finds the map",
        target_length="500 words",
    )

    messages = build_render_messages(session, story_id, scene.id)
    scene_content = messages[-1]["content"]

    assert scene_content.startswith("## Scene Brief")
    heading_index = scene_content.index("Heading: Arrival")
    pov_index = scene_content.index("Point of view: Mara")
    brief_index = scene_content.index("Brief: First")
    required_actions_index = scene_content.index("Required actions: Knock on the door")
    desired_outcome_index = scene_content.index("Desired outcome: Mara finds the map")
    target_length_index = scene_content.index("Target length: 500 words")
    assert (
        heading_index
        < pov_index
        < brief_index
        < required_actions_index
        < desired_outcome_index
        < target_length_index
    )


def test_build_render_messages_system_message_has_generation_guideance(session, story_id):
    update_story(session, story_id, generation_guideance="No profanity")
    scene = create_scene(session, story_id=story_id, position=0, brief="First")

    messages = build_render_messages(session, story_id, scene.id)

    assert "## Generation Guidance\n\nNo profanity" in messages[0]["content"]


def test_build_render_messages_system_message_includes_only_assigned_reference_cards(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="First")
    assigned_character = create_character(
        session, story_id=story_id, name="Alex", description="A wanderer", motive="Find home"
    )
    assigned_location = create_location(session, story_id=story_id, name="The Tavern", description="A cozy inn")
    assign_character(session, scene.id, assigned_character.id)
    assign_location(session, scene.id, assigned_location.id)
    create_character(session, story_id=story_id, name="Unassigned Character")
    create_location(session, story_id=story_id, name="Unassigned Location")

    messages = build_render_messages(session, story_id, scene.id)

    system_content = messages[0]["content"]
    assert "## Cast of Characters" in system_content
    assert "CHARACTER: Alex" in system_content
    assert "Enduring details: A wanderer" in system_content
    assert "Core motive: Find home" in system_content
    assert "## Locations" in system_content
    assert "LOCATION: The Tavern" in system_content
    assert "A cozy inn" in system_content
    assert "Unassigned Character" not in system_content
    assert "Unassigned Location" not in system_content
    assert system_content.index("## Cast of Characters") < system_content.index("CHARACTER: Alex")
    assert system_content.index("## Locations") < system_content.index("LOCATION: The Tavern")


def test_build_render_messages_system_message_omits_reference_headings_when_none_assigned(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="First")

    messages = build_render_messages(session, story_id, scene.id)

    system_content = messages[0]["content"]
    assert "## Cast of Characters" not in system_content
    assert "## Locations" not in system_content


def test_build_render_messages_does_not_raise_when_prior_scene_has_no_active_rendering(session, story_id):
    create_scene(session, story_id=story_id, position=0, brief="First")
    second = create_scene(session, story_id=story_id, position=1, brief="Second")

    messages = build_render_messages(session, story_id, second.id)

    assert "## Optional Recent Prose" not in messages[1]["content"]


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
        RenderComplete(text="The scene.", reasoning="Thinking..."),
    ]


def test_stream_render_aggregates_reasoning_across_multiple_chunks(monkeypatch):
    script_stream(
        monkeypatch,
        [
            make_chunk(reasoning_content="First, "),
            make_chunk(reasoning_content="then second."),
            make_chunk(content="The scene."),
        ],
    )

    events = list(stream_render(make_config(), []))

    assert events[-1] == RenderComplete(text="The scene.", reasoning="First, then second.")


def test_stream_render_with_no_reasoning_deltas_yields_empty_reasoning(monkeypatch):
    script_stream(monkeypatch, [make_chunk(content="Once "), make_chunk(content="upon a time.")])

    events = list(stream_render(make_config(), []))

    assert events[-1] == RenderComplete(text="Once upon a time.", reasoning="")


def test_stream_render_empty_stream_yields_only_complete(monkeypatch):
    script_stream(monkeypatch, [])

    events = list(stream_render(make_config(), []))

    assert events == [RenderComplete(text="", reasoning="")]
