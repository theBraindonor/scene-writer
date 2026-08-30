import pytest

import scene.data.database as database_module
from scene.agent.application.state import ApplicationState, ApplicationTab
from scene.agent.application.tools.location import build_location_tools
from scene.core.location import create_location
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
def seeded_location_id(seeded_story_id):
    with session_scope() as session:
        location = create_location(session, story_id=seeded_story_id, name="Old Tower")
        return location.id


def tools_by_name(state):
    return {tool.name: tool for tool in build_location_tools(state)}


def _not_found(location_id):
    return {"error": f"Location {location_id} not found"}


def test_create_location_requires_an_open_story(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["create_location"].handler({"name": "Old Tower", "description": "A crumbling ruin"})

    assert result["story_id"] == seeded_story_id
    assert result["name"] == "Old Tower"
    assert result["description"] == "A crumbling ruin"
    assert state.current_location_id == result["id"]
    assert state.current_tab is ApplicationTab.LOCATIONS


def test_create_location_with_no_open_story_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["create_location"].handler({"name": "Old Tower"})

    assert "No story is open" in result["error"]


def test_list_locations_uses_the_open_story(seeded_story_id, seeded_location_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["list_locations"].handler({})

    assert [location["id"] for location in result["locations"]] == [seeded_location_id]


def test_list_locations_with_no_open_story_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["list_locations"].handler({})

    assert "No story is open" in result["error"]


def test_update_location_changes_only_given_fields_and_selects_it(seeded_story_id, seeded_location_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["update_location"].handler({"location_id": seeded_location_id, "name": "New Tower"})

    assert result["name"] == "New Tower"
    assert state.current_location_id == seeded_location_id
    assert state.current_tab is ApplicationTab.LOCATIONS


def test_update_location_missing_location_id_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["update_location"].handler({"name": "New Tower"})

    assert "location_id" in result["error"]


def test_update_location_not_found_returns_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["update_location"].handler({"location_id": 999, "name": "New Tower"})

    assert result == _not_found(999)


def test_delete_location_removes_location_and_clears_selection(seeded_location_id):
    state = ApplicationState(current_location_id=seeded_location_id)
    tools = tools_by_name(state)

    result = tools["delete_location"].handler({"location_id": seeded_location_id})

    assert result == {"deleted": True, "id": seeded_location_id}
    assert state.current_location_id is None
    assert state.current_tab is ApplicationTab.LOCATIONS


def test_delete_location_missing_location_id_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["delete_location"].handler({})

    assert "location_id" in result["error"]


def test_delete_location_not_found_returns_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["delete_location"].handler({"location_id": 999})

    assert result == _not_found(999)


def test_location_tools_have_no_story_id_parameter():
    for tool in build_location_tools(ApplicationState()):
        assert "story_id" not in tool.schema["function"]["parameters"]["properties"]


def test_tool_schemas_declare_function_name_matching_tool_name():
    for tool in build_location_tools(ApplicationState()):
        assert tool.schema["type"] == "function"
        assert tool.schema["function"]["name"] == tool.name
