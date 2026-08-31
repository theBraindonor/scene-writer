import pytest

import scene.agent.application.tools.render as render_module
import scene.data.database as database_module
from scene.agent.application.state import ApplicationState, ApplicationTab
from scene.agent.application.tools.render import AgentRenderRequest, build_render_tools
from scene.agent.config import LLMConfig
from scene.core.scene import create_scene
from scene.core.story import create_story
from scene.data.database import session_scope

RENDERING_CONFIG = LLMConfig(model="fake-rendering-model", api_base=None, api_key=None)

_NO_SELECTED_SCENE = {
    "error": "No scene is selected. Select one with select_scene, or create one with create_scene."
}
_RENDERING_NOT_CONFIGURED = {"error": "Rendering is not configured. See the Rendering panel for details."}
_EARLIER_SCENE_UNRENDERED = {"error": "An earlier scene has no active rendering yet. Render it first."}


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


@pytest.fixture
def seeded_story_id():
    with session_scope() as session:
        story = create_story(session, title="Seed Story", story_brief="A seeded story brief")
        return story.id


@pytest.fixture
def seeded_scene_id(seeded_story_id):
    with session_scope() as session:
        scene = create_scene(session, story_id=seeded_story_id, position=0, brief="A first scene")
        return scene.id


def immediate_request_render(result):
    """A fake bridge: fills in the request's result and marks it done synchronously, as if the
    main-thread render had already settled by the time it's called."""

    def request_render(request: AgentRenderRequest) -> None:
        request.result.update(result)
        request.done.set()

    return request_render


def never_completes_request_render(request: AgentRenderRequest) -> None:
    pass


def tools_by_name(state, request_render, rendering_config=RENDERING_CONFIG):
    return {tool.name: tool for tool in build_render_tools(state, rendering_config, request_render)}


def test_render_scene_without_selection_returns_error(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state, immediate_request_render({"body": "unused"}))

    result = tools["render_scene"].handler({})

    assert result == _NO_SELECTED_SCENE


def test_render_scene_without_rendering_config_returns_error(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state, immediate_request_render({"body": "unused"}), rendering_config=None)

    result = tools["render_scene"].handler({})

    assert result == _RENDERING_NOT_CONFIGURED


def test_render_scene_not_found_returns_error(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=999)
    tools = tools_by_name(state, immediate_request_render({"body": "unused"}))

    result = tools["render_scene"].handler({})

    assert result == {"error": "Scene 999 not found"}


def test_render_scene_with_earlier_scene_unrendered_returns_error(seeded_story_id, seeded_scene_id):
    with session_scope() as session:
        second = create_scene(session, story_id=seeded_story_id, position=1, brief="A second scene")
        second_id = second.id

    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=second_id)
    tools = tools_by_name(state, immediate_request_render({"body": "unused"}))

    result = tools["render_scene"].handler({})

    assert result == _EARLIER_SCENE_UNRENDERED


def test_render_scene_forwards_request_and_returns_body(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(
        state, immediate_request_render({"body": "Generated prose.", "error": None, "cancelled": False})
    )

    result = tools["render_scene"].handler({})

    assert result == {"scene_id": seeded_scene_id, "body": "Generated prose."}
    assert state.current_tab is ApplicationTab.SCENES


def test_render_scene_reports_error_from_result(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state, immediate_request_render({"error": "boom"}))

    result = tools["render_scene"].handler({})

    assert result == {"error": "Rendering failed: boom"}


def test_render_scene_reports_cancellation(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(
        state, immediate_request_render({"cancelled": True, "body": "Partial prose...", "error": None})
    )

    result = tools["render_scene"].handler({})

    assert result == {"cancelled": True, "partial_body": "Partial prose..."}


def test_render_scene_reports_continuity_warning(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(
        state,
        immediate_request_render(
            {"body": "Generated prose.", "error": None, "cancelled": False, "continuity_error": "continuity down"}
        ),
    )

    result = tools["render_scene"].handler({})

    assert result["scene_id"] == seeded_scene_id
    assert result["body"] == "Generated prose."
    assert "continuity down" in result["continuity_warning"]


def test_render_scene_times_out_when_request_never_completes(monkeypatch, seeded_story_id, seeded_scene_id):
    monkeypatch.setattr(render_module, "RENDER_TIMEOUT_SECONDS", 0.05)
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state, never_completes_request_render)

    result = tools["render_scene"].handler({})

    assert result == {"error": "Rendering is taking longer than expected and is still running in the background."}
