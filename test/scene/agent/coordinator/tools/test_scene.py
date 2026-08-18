import pytest

import scene.data.database as database_module
from scene.agent.coordinator.state import CoordinatorState
from scene.agent.coordinator.tools.scene import build_scene_tools
from scene.core.scene import create_scene
from scene.core.story import create_story
from scene.data.database import session_scope


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


@pytest.fixture
def seeded_story_id():
    with session_scope() as session:
        story = create_story(session, title="Seed Story", scenario="A seeded scenario")
        return story.id


@pytest.fixture
def seeded_scene_id(seeded_story_id):
    with session_scope() as session:
        scene = create_scene(session, story_id=seeded_story_id, position=0, description="A first scene")
        return scene.id


def tools_by_name(state):
    return {tool.name: tool for tool in build_scene_tools(state)}


def _not_found(scene_id):
    return {"error": f"Scene {scene_id} not found"}


def test_create_scene_uses_explicit_story_id(seeded_story_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["create_scene"].handler(
        {"story_id": seeded_story_id, "position": 0, "description": "A new scene", "heading": "Opening"}
    )

    assert result["story_id"] == seeded_story_id
    assert result["position"] == 0
    assert result["description"] == "A new scene"
    assert result["heading"] == "Opening"


def test_create_scene_defaults_to_current_story(seeded_story_id):
    state = CoordinatorState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["create_scene"].handler({"position": 0, "description": "A new scene"})

    assert result["story_id"] == seeded_story_id


def test_create_scene_with_no_current_story_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["create_scene"].handler({"position": 0, "description": "A new scene"})

    assert "No current story" in result["error"]


def test_get_scene_returns_scene(seeded_scene_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["get_scene"].handler({"scene_id": seeded_scene_id})

    assert result["id"] == seeded_scene_id
    assert result["description"] == "A first scene"


def test_get_scene_missing_scene_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["get_scene"].handler({})

    assert "scene_id" in result["error"]


def test_get_scene_not_found_returns_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["get_scene"].handler({"scene_id": 999})

    assert result == {"error": "Scene 999 not found"}


def test_list_scenes_uses_explicit_story_id(seeded_story_id, seeded_scene_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["list_scenes"].handler({"story_id": seeded_story_id})

    assert [scene["id"] for scene in result["scenes"]] == [seeded_scene_id]


def test_list_scenes_defaults_to_current_story(seeded_story_id, seeded_scene_id):
    state = CoordinatorState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["list_scenes"].handler({})

    assert [scene["id"] for scene in result["scenes"]] == [seeded_scene_id]


def test_list_scenes_with_no_current_story_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["list_scenes"].handler({})

    assert "No current story" in result["error"]


def test_update_scene_changes_only_given_fields(seeded_scene_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["update_scene"].handler({"scene_id": seeded_scene_id, "heading": "Renamed"})

    assert result["heading"] == "Renamed"
    assert result["description"] == "A first scene"


def test_update_scene_missing_scene_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["update_scene"].handler({"heading": "Renamed"})

    assert "scene_id" in result["error"]


def test_update_scene_not_found_returns_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["update_scene"].handler({"scene_id": 999, "heading": "Renamed"})

    assert result == {"error": "Scene 999 not found"}


def test_delete_scene_removes_scene(seeded_scene_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["delete_scene"].handler({"scene_id": seeded_scene_id})

    assert result == {"deleted": True, "id": seeded_scene_id}
    assert tools["get_scene"].handler({"scene_id": seeded_scene_id}) == _not_found(seeded_scene_id)


def test_delete_scene_missing_scene_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["delete_scene"].handler({})

    assert "scene_id" in result["error"]


def test_delete_scene_not_found_returns_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["delete_scene"].handler({"scene_id": 999})

    assert result == {"error": "Scene 999 not found"}


def test_tool_schemas_declare_function_name_matching_tool_name():
    for tool in build_scene_tools(CoordinatorState()):
        assert tool.schema["type"] == "function"
        assert tool.schema["function"]["name"] == tool.name
