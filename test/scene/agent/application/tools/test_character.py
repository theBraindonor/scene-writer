import pytest

import scene.data.database as database_module
from scene.agent.application.state import ApplicationState, ApplicationTab
from scene.agent.application.tools.character import build_character_tools
from scene.core.character import create_character
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
def seeded_character_id(seeded_story_id):
    with session_scope() as session:
        character = create_character(session, story_id=seeded_story_id, name="Alex")
        return character.id


def tools_by_name(state):
    return {tool.name: tool for tool in build_character_tools(state)}


def _not_found(character_id):
    return {"error": f"Character {character_id} not found"}


def test_create_character_requires_an_open_story(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["create_character"].handler(
        {"name": "Alex", "description": "A wanderer", "motive": "Find home"}
    )

    assert result["story_id"] == seeded_story_id
    assert result["name"] == "Alex"
    assert result["description"] == "A wanderer"
    assert result["motive"] == "Find home"
    assert state.current_character_id == result["id"]
    assert state.current_tab is ApplicationTab.CHARACTERS


def test_create_character_with_no_open_story_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["create_character"].handler({"name": "Alex"})

    assert "No story is open" in result["error"]


def test_list_characters_uses_the_open_story(seeded_story_id, seeded_character_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["list_characters"].handler({})

    assert [character["id"] for character in result["characters"]] == [seeded_character_id]


def test_list_characters_with_no_open_story_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["list_characters"].handler({})

    assert "No story is open" in result["error"]


def test_update_character_changes_only_given_fields_and_selects_it(seeded_story_id, seeded_character_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["update_character"].handler({"character_id": seeded_character_id, "motive": "Revenge"})

    assert result["name"] == "Alex"
    assert result["motive"] == "Revenge"
    assert state.current_character_id == seeded_character_id
    assert state.current_tab is ApplicationTab.CHARACTERS


def test_update_character_missing_character_id_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["update_character"].handler({"motive": "Revenge"})

    assert "character_id" in result["error"]


def test_update_character_not_found_returns_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["update_character"].handler({"character_id": 999, "motive": "Revenge"})

    assert result == _not_found(999)


def test_delete_character_removes_character_and_clears_selection(seeded_character_id):
    state = ApplicationState(current_character_id=seeded_character_id)
    tools = tools_by_name(state)

    result = tools["delete_character"].handler({"character_id": seeded_character_id})

    assert result == {"deleted": True, "id": seeded_character_id}
    assert state.current_character_id is None
    assert state.current_tab is ApplicationTab.CHARACTERS


def test_delete_character_missing_character_id_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["delete_character"].handler({})

    assert "character_id" in result["error"]


def test_delete_character_not_found_returns_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["delete_character"].handler({"character_id": 999})

    assert result == _not_found(999)


def test_character_tools_have_no_story_id_parameter():
    for tool in build_character_tools(ApplicationState()):
        assert "story_id" not in tool.schema["function"]["parameters"]["properties"]


def test_tool_schemas_declare_function_name_matching_tool_name():
    for tool in build_character_tools(ApplicationState()):
        assert tool.schema["type"] == "function"
        assert tool.schema["function"]["name"] == tool.name
