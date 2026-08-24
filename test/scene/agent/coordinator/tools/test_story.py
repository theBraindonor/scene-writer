import pytest

import scene.data.database as database_module
from scene.agent.coordinator.state import CoordinatorState
from scene.agent.coordinator.tools.story import build_story_tools
from scene.core.story import archive_story, create_story
from scene.data.database import session_scope


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


@pytest.fixture
def seeded_story_id():
    with session_scope() as session:
        story = create_story(session, title="Seed Story", story_brief="A seeded story brief")
        return story.id


def tools_by_name(state):
    return {tool.name: tool for tool in build_story_tools(state)}


def test_create_story_returns_new_story_and_becomes_current():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["create_story"].handler({"title": "New Story", "story_brief": "A new story brief"})

    assert result["title"] == "New Story"
    assert result["story_brief"] == "A new story brief"
    assert result["is_archived"] is False
    assert state.current_story_id == result["id"]


def test_create_story_with_generation_guideance():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["create_story"].handler(
        {"title": "New Story", "story_brief": "A new story brief", "generation_guideance": "No profanity"}
    )

    assert result["generation_guideance"] == "No profanity"


def test_get_story_uses_current_story_id_when_omitted(seeded_story_id):
    state = CoordinatorState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["get_story"].handler({})

    assert result["id"] == seeded_story_id
    assert result["title"] == "Seed Story"


def test_get_story_explicit_story_id_switches_current(seeded_story_id):
    state = CoordinatorState(current_story_id=999)
    tools = tools_by_name(state)

    result = tools["get_story"].handler({"story_id": seeded_story_id})

    assert result["id"] == seeded_story_id
    assert state.current_story_id == seeded_story_id


def test_get_story_with_no_current_story_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["get_story"].handler({})

    assert "No current story" in result["error"]


def test_get_story_not_found_returns_error_and_does_not_change_current():
    state = CoordinatorState(current_story_id=1)
    tools = tools_by_name(state)

    result = tools["get_story"].handler({"story_id": 999})

    assert result == {"error": "Story 999 not found"}
    assert state.current_story_id == 1


def test_list_stories_excludes_archived_by_default(seeded_story_id):
    with session_scope() as session:
        archive_story(session, seeded_story_id)

    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["list_stories"].handler({})

    assert result["stories"] == []


def test_list_stories_includes_archived_when_requested(seeded_story_id):
    with session_scope() as session:
        archive_story(session, seeded_story_id)

    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["list_stories"].handler({"include_archived": True})

    assert [story["id"] for story in result["stories"]] == [seeded_story_id]


def test_list_stories_does_not_change_current_story(seeded_story_id):
    state = CoordinatorState()
    tools = tools_by_name(state)

    tools["list_stories"].handler({})

    assert state.current_story_id is None


def test_update_story_changes_only_given_fields_using_current_story(seeded_story_id):
    state = CoordinatorState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["update_story"].handler({"story_brief": "An updated story brief"})

    assert result["title"] == "Seed Story"
    assert result["story_brief"] == "An updated story brief"


def test_update_story_not_found_returns_error():
    state = CoordinatorState(current_story_id=999)
    tools = tools_by_name(state)

    result = tools["update_story"].handler({"title": "New Title"})

    assert result == {"error": "Story 999 not found"}


def test_update_story_with_no_current_story_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["update_story"].handler({"title": "New Title"})

    assert "No current story" in result["error"]


def test_archive_and_unarchive_story_round_trip_using_current_story(seeded_story_id):
    state = CoordinatorState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    archived = tools["archive_story"].handler({})
    assert archived["is_archived"] is True

    unarchived = tools["unarchive_story"].handler({})
    assert unarchived["is_archived"] is False


def test_archive_story_not_found_returns_error():
    state = CoordinatorState(current_story_id=999)
    tools = tools_by_name(state)

    result = tools["archive_story"].handler({})

    assert result == {"error": "Story 999 not found"}


def test_archive_story_with_no_current_story_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["archive_story"].handler({})

    assert "No current story" in result["error"]


def test_unarchive_story_not_found_returns_error():
    state = CoordinatorState(current_story_id=999)
    tools = tools_by_name(state)

    result = tools["unarchive_story"].handler({})

    assert result == {"error": "Story 999 not found"}


def test_unarchive_story_with_no_current_story_returns_clear_error():
    state = CoordinatorState()
    tools = tools_by_name(state)

    result = tools["unarchive_story"].handler({})

    assert "No current story" in result["error"]


def test_switching_between_two_stories_updates_current(seeded_story_id):
    with session_scope() as session:
        other = create_story(session, title="Other Story", story_brief="Another story brief")
        other_id = other.id

    state = CoordinatorState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    tools["get_story"].handler({"story_id": other_id})
    assert state.current_story_id == other_id

    result = tools["update_story"].handler({"title": "Renamed"})
    assert result["id"] == other_id
    assert result["title"] == "Renamed"


def test_tool_schemas_declare_function_name_matching_tool_name():
    for tool in build_story_tools(CoordinatorState()):
        assert tool.schema["type"] == "function"
        assert tool.schema["function"]["name"] == tool.name
