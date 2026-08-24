import pytest

import scene.data.database as database_module
from scene.agent.coordinator.state import CoordinatorState
from scene.agent.coordinator.tools.character import build_character_tools
from scene.core.character import create_character
from scene.core.scene import create_scene
from scene.core.story import create_story
from scene.data.database import session_scope


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


@pytest.fixture
def seeded_story_id():
    with session_scope() as session:
        story = create_story(session, title="Seed Story", story_brief="A seeded story brief")
        return story.id


@pytest.fixture
def other_story_id():
    with session_scope() as session:
        story = create_story(session, title="Other Story", story_brief="Another story brief")
        return story.id


@pytest.fixture
def seeded_character_id(seeded_story_id):
    with session_scope() as session:
        character = create_character(session, story_id=seeded_story_id, name="Alex")
        return character.id


@pytest.fixture
def seeded_scene_id(seeded_story_id):
    with session_scope() as session:
        scene = create_scene(session, story_id=seeded_story_id, position=0, brief="A first scene")
        return scene.id


def tools_by_name(state):
    return {tool.name: tool for tool in build_character_tools(state)}


def _not_found(character_id):
    return {"error": f"Character {character_id} not found"}


def test_create_character_uses_explicit_story_id(seeded_story_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["create_character"].handler(
        {"story_id": seeded_story_id, "name": "Alex", "description": "A wanderer", "motive": "Find home"}
    )

    assert result["story_id"] == seeded_story_id
    assert result["name"] == "Alex"
    assert result["description"] == "A wanderer"
    assert result["motive"] == "Find home"


def test_create_character_defaults_to_current_story(seeded_story_id):
    state = CoordinatorState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["create_character"].handler({"name": "Alex"})

    assert result["story_id"] == seeded_story_id


def test_create_character_with_no_current_story_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["create_character"].handler({"name": "Alex"})

    assert "No current story" in result["error"]


def test_get_character_returns_character(seeded_character_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["get_character"].handler({"character_id": seeded_character_id})

    assert result["id"] == seeded_character_id
    assert result["name"] == "Alex"


def test_get_character_missing_character_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["get_character"].handler({})

    assert "character_id" in result["error"]


def test_get_character_not_found_returns_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["get_character"].handler({"character_id": 999})

    assert result == _not_found(999)


def test_list_characters_uses_explicit_story_id(seeded_story_id, seeded_character_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["list_characters"].handler({"story_id": seeded_story_id})

    assert [character["id"] for character in result["characters"]] == [seeded_character_id]


def test_list_characters_defaults_to_current_story(seeded_story_id, seeded_character_id):
    state = CoordinatorState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["list_characters"].handler({})

    assert [character["id"] for character in result["characters"]] == [seeded_character_id]


def test_list_characters_with_no_current_story_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["list_characters"].handler({})

    assert "No current story" in result["error"]


def test_update_character_changes_only_given_fields(seeded_character_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["update_character"].handler({"character_id": seeded_character_id, "motive": "Revenge"})

    assert result["name"] == "Alex"
    assert result["motive"] == "Revenge"


def test_update_character_missing_character_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["update_character"].handler({"motive": "Revenge"})

    assert "character_id" in result["error"]


def test_update_character_not_found_returns_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["update_character"].handler({"character_id": 999, "motive": "Revenge"})

    assert result == _not_found(999)


def test_delete_character_removes_character(seeded_character_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["delete_character"].handler({"character_id": seeded_character_id})

    assert result == {"deleted": True, "id": seeded_character_id}
    assert tools["get_character"].handler({"character_id": seeded_character_id}) == _not_found(seeded_character_id)


def test_delete_character_missing_character_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["delete_character"].handler({})

    assert "character_id" in result["error"]


def test_delete_character_not_found_returns_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["delete_character"].handler({"character_id": 999})

    assert result == _not_found(999)


def test_assign_character_adds_character_to_scene(seeded_scene_id, seeded_character_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["assign_character"].handler({"scene_id": seeded_scene_id, "character_id": seeded_character_id})

    assert result == {"assigned": True, "scene_id": seeded_scene_id, "character_id": seeded_character_id}
    listed = tools["list_characters_for_scene"].handler({"scene_id": seeded_scene_id})
    assert [character["id"] for character in listed["characters"]] == [seeded_character_id]


def test_assign_character_missing_scene_id_returns_clear_error(seeded_character_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["assign_character"].handler({"character_id": seeded_character_id})

    assert "scene_id" in result["error"]


def test_assign_character_missing_character_id_returns_clear_error(seeded_scene_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["assign_character"].handler({"scene_id": seeded_scene_id})

    assert "character_id" in result["error"]


def test_assign_character_missing_scene_returns_tool_error(seeded_character_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["assign_character"].handler({"scene_id": 999, "character_id": seeded_character_id})

    assert "not found" in result["error"]


def test_assign_character_cross_story_returns_tool_error(seeded_scene_id, other_story_id):
    with session_scope() as session:
        other_character = create_character(session, story_id=other_story_id, name="Other")
        other_character_id = other_character.id

    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["assign_character"].handler({"scene_id": seeded_scene_id, "character_id": other_character_id})

    assert "different stories" in result["error"]


def test_unassign_character_removes_character_from_scene(seeded_scene_id, seeded_character_id):
    state = CoordinatorState()
    tools = tools_by_name(state)
    tools["assign_character"].handler({"scene_id": seeded_scene_id, "character_id": seeded_character_id})

    result = tools["unassign_character"].handler({"scene_id": seeded_scene_id, "character_id": seeded_character_id})

    assert result == {"assigned": False, "scene_id": seeded_scene_id, "character_id": seeded_character_id}
    listed = tools["list_characters_for_scene"].handler({"scene_id": seeded_scene_id})
    assert listed["characters"] == []


def test_unassign_character_missing_scene_id_returns_clear_error(seeded_character_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["unassign_character"].handler({"character_id": seeded_character_id})

    assert "scene_id" in result["error"]


def test_unassign_character_missing_character_id_returns_clear_error(seeded_scene_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["unassign_character"].handler({"scene_id": seeded_scene_id})

    assert "character_id" in result["error"]


def test_unassign_character_not_assigned_returns_error(seeded_scene_id, seeded_character_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["unassign_character"].handler({"scene_id": seeded_scene_id, "character_id": seeded_character_id})

    assert "not assigned" in result["error"]


def test_list_characters_for_scene_missing_scene_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["list_characters_for_scene"].handler({})

    assert "scene_id" in result["error"]


def test_list_scenes_for_character_returns_assigned_scenes(seeded_scene_id, seeded_character_id):
    state = CoordinatorState()
    tools = tools_by_name(state)
    tools["assign_character"].handler({"scene_id": seeded_scene_id, "character_id": seeded_character_id})

    result = tools["list_scenes_for_character"].handler({"character_id": seeded_character_id})

    assert [scene["id"] for scene in result["scenes"]] == [seeded_scene_id]


def test_list_scenes_for_character_missing_character_id_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["list_scenes_for_character"].handler({})

    assert "character_id" in result["error"]


def test_tool_schemas_declare_function_name_matching_tool_name():
    for tool in build_character_tools(CoordinatorState()):
        assert tool.schema["type"] == "function"
        assert tool.schema["function"]["name"] == tool.name
