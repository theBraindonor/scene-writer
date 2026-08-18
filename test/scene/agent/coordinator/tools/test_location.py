import pytest

import scene.data.database as database_module
from scene.agent.coordinator.state import CoordinatorState
from scene.agent.coordinator.tools.location import build_location_tools
from scene.core.location import create_location
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
def other_story_id():
    with session_scope() as session:
        story = create_story(session, title="Other Story", scenario="Another scenario")
        return story.id


@pytest.fixture
def seeded_location_id(seeded_story_id):
    with session_scope() as session:
        location = create_location(session, story_id=seeded_story_id, name="The Tavern")
        return location.id


@pytest.fixture
def seeded_scene_id(seeded_story_id):
    with session_scope() as session:
        scene = create_scene(session, story_id=seeded_story_id, position=0, description="A first scene")
        return scene.id


def tools_by_name(state):
    return {tool.name: tool for tool in build_location_tools(state)}


def _not_found(location_id):
    return {"error": f"Location {location_id} not found"}


def test_create_location_uses_explicit_story_id(seeded_story_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["create_location"].handler(
        {"story_id": seeded_story_id, "name": "The Tavern", "description": "A cozy inn"}
    )

    assert result["story_id"] == seeded_story_id
    assert result["name"] == "The Tavern"
    assert result["description"] == "A cozy inn"


def test_create_location_defaults_to_current_story(seeded_story_id):
    state = CoordinatorState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["create_location"].handler({"name": "The Tavern"})

    assert result["story_id"] == seeded_story_id


def test_create_location_with_no_current_story_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["create_location"].handler({"name": "The Tavern"})

    assert "No current story" in result["error"]


def test_get_location_returns_location(seeded_location_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["get_location"].handler({"location_id": seeded_location_id})

    assert result["id"] == seeded_location_id
    assert result["name"] == "The Tavern"


def test_get_location_missing_location_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["get_location"].handler({})

    assert "location_id" in result["error"]


def test_get_location_not_found_returns_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["get_location"].handler({"location_id": 999})

    assert result == _not_found(999)


def test_list_locations_uses_explicit_story_id(seeded_story_id, seeded_location_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["list_locations"].handler({"story_id": seeded_story_id})

    assert [location["id"] for location in result["locations"]] == [seeded_location_id]


def test_list_locations_defaults_to_current_story(seeded_story_id, seeded_location_id):
    state = CoordinatorState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["list_locations"].handler({})

    assert [location["id"] for location in result["locations"]] == [seeded_location_id]


def test_list_locations_with_no_current_story_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["list_locations"].handler({})

    assert "No current story" in result["error"]


def test_update_location_changes_only_given_fields(seeded_location_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["update_location"].handler({"location_id": seeded_location_id, "description": "Now abandoned"})

    assert result["name"] == "The Tavern"
    assert result["description"] == "Now abandoned"


def test_update_location_missing_location_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["update_location"].handler({"description": "Now abandoned"})

    assert "location_id" in result["error"]


def test_update_location_not_found_returns_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["update_location"].handler({"location_id": 999, "description": "Now abandoned"})

    assert result == _not_found(999)


def test_delete_location_removes_location(seeded_location_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["delete_location"].handler({"location_id": seeded_location_id})

    assert result == {"deleted": True, "id": seeded_location_id}
    assert tools["get_location"].handler({"location_id": seeded_location_id}) == _not_found(seeded_location_id)


def test_delete_location_missing_location_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["delete_location"].handler({})

    assert "location_id" in result["error"]


def test_delete_location_not_found_returns_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["delete_location"].handler({"location_id": 999})

    assert result == _not_found(999)


def test_assign_location_adds_location_to_scene(seeded_scene_id, seeded_location_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["assign_location"].handler({"scene_id": seeded_scene_id, "location_id": seeded_location_id})

    assert result == {"assigned": True, "scene_id": seeded_scene_id, "location_id": seeded_location_id}
    listed = tools["list_locations_for_scene"].handler({"scene_id": seeded_scene_id})
    assert [location["id"] for location in listed["locations"]] == [seeded_location_id]


def test_assign_location_missing_scene_id_returns_clear_error(seeded_location_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["assign_location"].handler({"location_id": seeded_location_id})

    assert "scene_id" in result["error"]


def test_assign_location_missing_location_id_returns_clear_error(seeded_scene_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["assign_location"].handler({"scene_id": seeded_scene_id})

    assert "location_id" in result["error"]


def test_assign_location_missing_scene_returns_tool_error(seeded_location_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["assign_location"].handler({"scene_id": 999, "location_id": seeded_location_id})

    assert "not found" in result["error"]


def test_assign_location_cross_story_returns_tool_error(seeded_scene_id, other_story_id):
    with session_scope() as session:
        other_location = create_location(session, story_id=other_story_id, name="Other Place")
        other_location_id = other_location.id

    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["assign_location"].handler({"scene_id": seeded_scene_id, "location_id": other_location_id})

    assert "different stories" in result["error"]


def test_unassign_location_removes_location_from_scene(seeded_scene_id, seeded_location_id):
    state = CoordinatorState()
    tools = tools_by_name(state)
    tools["assign_location"].handler({"scene_id": seeded_scene_id, "location_id": seeded_location_id})

    result = tools["unassign_location"].handler({"scene_id": seeded_scene_id, "location_id": seeded_location_id})

    assert result == {"assigned": False, "scene_id": seeded_scene_id, "location_id": seeded_location_id}
    listed = tools["list_locations_for_scene"].handler({"scene_id": seeded_scene_id})
    assert listed["locations"] == []


def test_unassign_location_missing_scene_id_returns_clear_error(seeded_location_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["unassign_location"].handler({"location_id": seeded_location_id})

    assert "scene_id" in result["error"]


def test_unassign_location_missing_location_id_returns_clear_error(seeded_scene_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["unassign_location"].handler({"scene_id": seeded_scene_id})

    assert "location_id" in result["error"]


def test_unassign_location_not_assigned_returns_error(seeded_scene_id, seeded_location_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["unassign_location"].handler({"scene_id": seeded_scene_id, "location_id": seeded_location_id})

    assert "not assigned" in result["error"]


def test_list_locations_for_scene_missing_scene_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["list_locations_for_scene"].handler({})

    assert "scene_id" in result["error"]


def test_list_scenes_for_location_returns_assigned_scenes(seeded_scene_id, seeded_location_id):
    state = CoordinatorState()
    tools = tools_by_name(state)
    tools["assign_location"].handler({"scene_id": seeded_scene_id, "location_id": seeded_location_id})

    result = tools["list_scenes_for_location"].handler({"location_id": seeded_location_id})

    assert [scene["id"] for scene in result["scenes"]] == [seeded_scene_id]


def test_list_scenes_for_location_missing_location_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["list_scenes_for_location"].handler({})

    assert "location_id" in result["error"]


def test_tool_schemas_declare_function_name_matching_tool_name():
    for tool in build_location_tools(CoordinatorState()):
        assert tool.schema["type"] == "function"
        assert tool.schema["function"]["name"] == tool.name
