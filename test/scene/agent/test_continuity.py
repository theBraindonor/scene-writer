from dataclasses import dataclass, field

import pytest

import scene.agent.continuity as continuity_module
from scene.agent.config import LLMConfig
from scene.agent.continuity import (
    NO_PRIOR_NARRATIVE_STATE,
    accept_scene,
    build_continuity_messages,
    regenerate_snapshots_from,
    run_continuity_edit,
)
from scene.core.continuity_snapshot import create_snapshot, get_snapshot
from scene.core.rendering import create_rendering, set_active_rendering
from scene.core.scene import create_scene
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
    return create_story(session, title="Title", story_brief="Story brief").id


def _activate(session, scene_id, body):
    rendering = create_rendering(session, scene_id=scene_id, body=body)
    set_active_rendering(session, rendering.id)
    return rendering


def make_config():
    return LLMConfig(model="openai/test-model", api_base=None, api_key=None)


def test_build_continuity_messages_with_no_prior_state(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="First")
    _activate(session, scene.id, "The prose of the first scene.")

    messages = build_continuity_messages(session, story_id, scene.id)

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert NO_PRIOR_NARRATIVE_STATE in messages[1]["content"]
    assert "The prose of the first scene." in messages[1]["content"]


def test_build_continuity_messages_with_prior_state(session, story_id):
    first = create_scene(session, story_id=story_id, position=0, brief="First")
    second = create_scene(session, story_id=story_id, position=1, brief="Second")
    _activate(session, first.id, "First scene prose.")
    create_snapshot(session, story_id, first.id, "Mara is at the station.")
    _activate(session, second.id, "Second scene prose.")

    messages = build_continuity_messages(session, story_id, second.id)

    assert "Mara is at the station." in messages[1]["content"]
    assert "Second scene prose." in messages[1]["content"]


def test_build_continuity_messages_raises_when_no_active_rendering(session, story_id):
    scene = create_scene(session, story_id=story_id, position=0, brief="First")

    with pytest.raises(ValueError, match="no active rendering"):
        build_continuity_messages(session, story_id, scene.id)


@dataclass
class FakeMessage:
    content: str


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeResponse:
    choices: list[FakeChoice] = field(default_factory=list)


def script_complete(monkeypatch, content):
    def fake_complete(config, messages, tools=None):
        return FakeResponse(choices=[FakeChoice(message=FakeMessage(content=content))])

    monkeypatch.setattr(continuity_module, "complete", fake_complete)


def test_run_continuity_edit_returns_response_content(monkeypatch):
    script_complete(monkeypatch, "Updated narrative state.")

    result = run_continuity_edit(make_config(), [])

    assert result == "Updated narrative state."


def test_accept_scene_creates_snapshot(session, story_id, monkeypatch):
    scene = create_scene(session, story_id=story_id, position=0, brief="First")
    _activate(session, scene.id, "First scene prose.")
    script_complete(monkeypatch, "Mara is at the station.")

    snapshot = accept_scene(make_config(), session, story_id, scene.id)

    assert snapshot.narrative_state == "Mara is at the station."
    assert get_snapshot(session, story_id, scene.id).narrative_state == "Mara is at the station."


def test_accept_scene_replaces_existing_snapshot(session, story_id, monkeypatch):
    scene = create_scene(session, story_id=story_id, position=0, brief="First")
    _activate(session, scene.id, "First scene prose.")
    script_complete(monkeypatch, "First state.")
    accept_scene(make_config(), session, story_id, scene.id)

    script_complete(monkeypatch, "Revised state.")
    accept_scene(make_config(), session, story_id, scene.id)

    assert get_snapshot(session, story_id, scene.id).narrative_state == "Revised state."


def test_regenerate_snapshots_from_invalidates_and_rebuilds_forward(session, story_id, monkeypatch):
    first = create_scene(session, story_id=story_id, position=0, brief="First")
    second = create_scene(session, story_id=story_id, position=1, brief="Second")
    _activate(session, first.id, "First scene prose.")
    _activate(session, second.id, "Second scene prose.")
    create_snapshot(session, story_id, first.id, "Stale state.")
    create_snapshot(session, story_id, second.id, "Stale state.")

    script_complete(monkeypatch, "Fresh state.")
    regenerate_snapshots_from(make_config(), session, story_id, from_position=0)

    assert get_snapshot(session, story_id, first.id).narrative_state == "Fresh state."
    assert get_snapshot(session, story_id, second.id).narrative_state == "Fresh state."


def test_regenerate_snapshots_from_stops_at_unrendered_scene(session, story_id, monkeypatch):
    first = create_scene(session, story_id=story_id, position=0, brief="First")
    create_scene(session, story_id=story_id, position=1, brief="Second")
    _activate(session, first.id, "First scene prose.")

    script_complete(monkeypatch, "Fresh state.")
    regenerate_snapshots_from(make_config(), session, story_id, from_position=0)

    assert get_snapshot(session, story_id, first.id) is not None


def test_regenerate_snapshots_from_only_affects_scenes_at_or_after_position(session, story_id, monkeypatch):
    first = create_scene(session, story_id=story_id, position=0, brief="First")
    second = create_scene(session, story_id=story_id, position=1, brief="Second")
    _activate(session, first.id, "First scene prose.")
    _activate(session, second.id, "Second scene prose.")
    create_snapshot(session, story_id, first.id, "Untouched state.")

    script_complete(monkeypatch, "Fresh state.")
    regenerate_snapshots_from(make_config(), session, story_id, from_position=1)

    assert get_snapshot(session, story_id, first.id).narrative_state == "Untouched state."
    assert get_snapshot(session, story_id, second.id).narrative_state == "Fresh state."
