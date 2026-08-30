import pytest

import scene.data.database as database_module
from scene.agent.application.state import ApplicationState, ApplicationTab
from scene.agent.application.tools.scene import build_scene_tools
from scene.core.character import create_character
from scene.core.location import create_location
from scene.core.scene import create_scene
from scene.core.scene_character import assign_character
from scene.core.scene_location import assign_location
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
def seeded_scene_id(seeded_story_id):
    with session_scope() as session:
        scene = create_scene(session, story_id=seeded_story_id, position=0, brief="A first scene")
        return scene.id


@pytest.fixture
def seeded_character_id(seeded_story_id):
    with session_scope() as session:
        character = create_character(session, story_id=seeded_story_id, name="Ada")
        return character.id


@pytest.fixture
def seeded_location_id(seeded_story_id):
    with session_scope() as session:
        location = create_location(session, story_id=seeded_story_id, name="The Archive")
        return location.id


def tools_by_name(state):
    return {tool.name: tool for tool in build_scene_tools(state)}


def _not_found(scene_id):
    return {"error": f"Scene {scene_id} not found"}


def test_create_scene_selects_it_and_switches_to_scenes_tab(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["create_scene"].handler({"brief": "A new scene", "heading": "Opening"})

    assert result["brief"] == "A new scene"
    assert result["heading"] == "Opening"
    assert result["position"] == 0
    assert result["is_selected"] is True
    assert state.current_scene_id == result["id"]
    assert state.current_tab is ApplicationTab.SCENES


def test_create_scene_defaults_position_to_end_of_story(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["create_scene"].handler({"brief": "A second scene"})

    assert result["position"] == 1


def test_create_scene_with_explicit_position(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["create_scene"].handler({"brief": "Placed deliberately", "position": 3})

    assert result["position"] == 3


def test_create_scene_with_invalid_pov_character_returns_tool_error(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["create_scene"].handler({"brief": "A scene", "pov_character_id": 999})

    assert "not found" in result["error"]


def test_create_scene_with_no_open_story_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["create_scene"].handler({"brief": "A scene"})

    assert "No story is open" in result["error"]


def test_list_scenes_flags_the_selected_scene_and_includes_cast(
    seeded_story_id, seeded_scene_id, seeded_character_id, seeded_location_id
):
    with session_scope() as session:
        assign_character(session, seeded_scene_id, seeded_character_id)
        assign_location(session, seeded_scene_id, seeded_location_id)

    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)

    result = tools["list_scenes"].handler({})

    scene = result["scenes"][0]
    assert scene["is_selected"] is True
    assert scene["characters"] == [{"id": seeded_character_id, "name": "Ada"}]
    assert scene["locations"] == [{"id": seeded_location_id, "name": "The Archive"}]


def test_list_scenes_with_no_open_story_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["list_scenes"].handler({})

    assert "No story is open" in result["error"]


def test_select_scene_selects_it_and_switches_to_scenes_tab(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["select_scene"].handler({"scene_id": seeded_scene_id})

    assert result["id"] == seeded_scene_id
    assert result["is_selected"] is True
    assert state.current_scene_id == seeded_scene_id
    assert state.current_tab is ApplicationTab.SCENES


def test_select_scene_missing_scene_id_returns_clear_error(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["select_scene"].handler({})

    assert "scene_id" in result["error"]


def test_select_scene_not_found_returns_error(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["select_scene"].handler({"scene_id": 999})

    assert result == _not_found(999)


def test_select_scene_from_a_different_story_returns_clear_error(seeded_story_id, other_story_id):
    with session_scope() as session:
        other_scene = create_scene(session, story_id=other_story_id, position=0, brief="Not this story")
        other_scene_id = other_scene.id

    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["select_scene"].handler({"scene_id": other_scene_id})

    assert "does not belong to the open story" in result["error"]
    assert state.current_scene_id is None


def test_select_scene_with_no_open_story_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["select_scene"].handler({"scene_id": 1})

    assert "No story is open" in result["error"]


def test_update_scene_has_no_scene_id_parameter_and_acts_on_selected_scene(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)

    result = tools["update_scene"].handler({"brief": "An updated brief"})

    assert result["brief"] == "An updated brief"
    assert state.current_tab is ApplicationTab.SCENES


def test_update_scene_with_invalid_pov_character_returns_tool_error(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)

    result = tools["update_scene"].handler({"pov_character_id": 999})

    assert "not found" in result["error"]


def test_update_scene_with_no_selected_scene_returns_clear_error(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["update_scene"].handler({"brief": "An updated brief"})

    assert "No scene is selected" in result["error"]


def test_update_scene_not_found_returns_error(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=999)
    tools = tools_by_name(state)

    result = tools["update_scene"].handler({"brief": "An updated brief"})

    assert result == _not_found(999)


def test_delete_scene_removes_scene_and_clears_selection(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)

    result = tools["delete_scene"].handler({})

    assert result == {"deleted": True, "id": seeded_scene_id}
    assert state.current_scene_id is None
    assert state.current_tab is ApplicationTab.SCENES


def test_delete_scene_with_no_selected_scene_returns_clear_error(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["delete_scene"].handler({})

    assert "No scene is selected" in result["error"]


def test_delete_scene_not_found_returns_error(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=999)
    tools = tools_by_name(state)

    result = tools["delete_scene"].handler({})

    assert result == _not_found(999)


def test_assign_character_to_scene_adds_character_and_returns_updated_cast(
    seeded_story_id, seeded_scene_id, seeded_character_id
):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)

    result = tools["assign_character_to_scene"].handler({"character_id": seeded_character_id})

    assert result["characters"] == [{"id": seeded_character_id, "name": "Ada"}]
    assert state.current_tab is ApplicationTab.SCENES


def test_assign_character_to_scene_missing_character_id_returns_clear_error(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)

    result = tools["assign_character_to_scene"].handler({})

    assert "character_id" in result["error"]


def test_assign_character_to_scene_with_no_selected_scene_returns_clear_error(seeded_character_id):
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["assign_character_to_scene"].handler({"character_id": seeded_character_id})

    assert "No scene is selected" in result["error"]


def test_assign_character_to_scene_is_idempotent_when_already_assigned(
    seeded_story_id, seeded_scene_id, seeded_character_id
):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)
    tools["assign_character_to_scene"].handler({"character_id": seeded_character_id})

    result = tools["assign_character_to_scene"].handler({"character_id": seeded_character_id})

    assert result["characters"] == [{"id": seeded_character_id, "name": "Ada"}]


def test_assign_character_to_scene_cross_story_returns_tool_error(
    seeded_story_id, seeded_scene_id, other_story_id
):
    with session_scope() as session:
        other_character = create_character(session, story_id=other_story_id, name="Other")
        other_character_id = other_character.id

    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)

    result = tools["assign_character_to_scene"].handler({"character_id": other_character_id})

    assert "different stories" in result["error"]


def test_unassign_character_from_scene_removes_character(seeded_story_id, seeded_scene_id, seeded_character_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)
    tools["assign_character_to_scene"].handler({"character_id": seeded_character_id})

    result = tools["unassign_character_from_scene"].handler({"character_id": seeded_character_id})

    assert result["characters"] == []


def test_unassign_character_from_scene_missing_character_id_returns_clear_error(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)

    result = tools["unassign_character_from_scene"].handler({})

    assert "character_id" in result["error"]


def test_unassign_character_from_scene_with_no_selected_scene_returns_clear_error(seeded_character_id):
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["unassign_character_from_scene"].handler({"character_id": seeded_character_id})

    assert "No scene is selected" in result["error"]


def test_assign_location_to_scene_adds_location_and_returns_updated_locations(
    seeded_story_id, seeded_scene_id, seeded_location_id
):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)

    result = tools["assign_location_to_scene"].handler({"location_id": seeded_location_id})

    assert result["locations"] == [{"id": seeded_location_id, "name": "The Archive"}]


def test_assign_location_to_scene_missing_location_id_returns_clear_error(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)

    result = tools["assign_location_to_scene"].handler({})

    assert "location_id" in result["error"]


def test_assign_location_to_scene_with_no_selected_scene_returns_clear_error(seeded_location_id):
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["assign_location_to_scene"].handler({"location_id": seeded_location_id})

    assert "No scene is selected" in result["error"]


def test_assign_location_to_scene_is_idempotent_when_already_assigned(
    seeded_story_id, seeded_scene_id, seeded_location_id
):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)
    tools["assign_location_to_scene"].handler({"location_id": seeded_location_id})

    result = tools["assign_location_to_scene"].handler({"location_id": seeded_location_id})

    assert result["locations"] == [{"id": seeded_location_id, "name": "The Archive"}]


def test_assign_location_to_scene_cross_story_returns_tool_error(seeded_story_id, seeded_scene_id, other_story_id):
    with session_scope() as session:
        other_location = create_location(session, story_id=other_story_id, name="Elsewhere")
        other_location_id = other_location.id

    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)

    result = tools["assign_location_to_scene"].handler({"location_id": other_location_id})

    assert "different stories" in result["error"]


def test_unassign_location_from_scene_removes_location(seeded_story_id, seeded_scene_id, seeded_location_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)
    tools["assign_location_to_scene"].handler({"location_id": seeded_location_id})

    result = tools["unassign_location_from_scene"].handler({"location_id": seeded_location_id})

    assert result["locations"] == []


def test_unassign_location_from_scene_missing_location_id_returns_clear_error(seeded_story_id, seeded_scene_id):
    state = ApplicationState(current_story_id=seeded_story_id, current_scene_id=seeded_scene_id)
    tools = tools_by_name(state)

    result = tools["unassign_location_from_scene"].handler({})

    assert "location_id" in result["error"]


def test_unassign_location_from_scene_with_no_selected_scene_returns_clear_error(seeded_location_id):
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["unassign_location_from_scene"].handler({"location_id": seeded_location_id})

    assert "No scene is selected" in result["error"]


def test_scene_tools_have_no_story_id_or_scene_id_parameter_except_select_and_create():
    for tool in build_scene_tools(ApplicationState()):
        properties = tool.schema["function"]["parameters"]["properties"]
        assert "story_id" not in properties
        if tool.name != "select_scene":
            assert "scene_id" not in properties


def test_tool_schemas_declare_function_name_matching_tool_name():
    for tool in build_scene_tools(ApplicationState()):
        assert tool.schema["type"] == "function"
        assert tool.schema["function"]["name"] == tool.name
