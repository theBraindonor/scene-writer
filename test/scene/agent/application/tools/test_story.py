import pytest

import scene.data.database as database_module
from scene.agent.application.state import ApplicationState, ApplicationTab
from scene.agent.application.tools.story import build_story_tools
from scene.core.story import archive_story, create_story, get_story
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


def test_create_story_returns_new_story_opens_it_and_switches_to_story_tab():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["create_story"].handler({"title": "New Story", "story_brief": "A new story brief"})

    assert result["title"] == "New Story"
    assert result["story_brief"] == "A new story brief"
    assert result["is_archived"] is False
    assert result["is_open"] is True
    assert state.current_story_id == result["id"]
    assert state.current_tab is ApplicationTab.STORY


def test_create_story_with_generation_guidance_translates_to_generation_guideance():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["create_story"].handler(
        {"title": "New Story", "story_brief": "A new story brief", "generation_guidance": "No profanity"}
    )

    assert result["generation_guidance"] == "No profanity"
    with session_scope() as session:
        assert get_story(session, result["id"]).generation_guideance == "No profanity"


def test_open_story_makes_it_current_and_switches_to_story_tab(seeded_story_id):
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["open_story"].handler({"story_id": seeded_story_id})

    assert result["id"] == seeded_story_id
    assert result["is_open"] is True
    assert state.current_story_id == seeded_story_id
    assert state.current_tab is ApplicationTab.STORY


def test_open_story_missing_story_id_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["open_story"].handler({})

    assert "story_id" in result["error"]


def test_open_story_not_found_returns_error_and_does_not_change_current():
    state = ApplicationState(current_story_id=1)
    tools = tools_by_name(state)

    result = tools["open_story"].handler({"story_id": 999})

    assert result == {"error": "Story 999 not found"}
    assert state.current_story_id == 1


def test_list_stories_flags_the_open_story(seeded_story_id):
    with session_scope() as session:
        other = create_story(session, title="Other Story", story_brief="Another story brief")
        other_id = other.id

    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["list_stories"].handler({})

    by_id = {story["id"]: story for story in result["stories"]}
    assert by_id[seeded_story_id]["is_open"] is True
    assert by_id[other_id]["is_open"] is False


def test_list_stories_filters_by_query(seeded_story_id):
    with session_scope() as session:
        create_story(session, title="Another Tale", story_brief="Another story brief")

    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["list_stories"].handler({"query": "seed"})

    assert [story["id"] for story in result["stories"]] == [seeded_story_id]


def test_list_stories_excludes_archived_by_default(seeded_story_id):
    with session_scope() as session:
        archive_story(session, seeded_story_id)

    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["list_stories"].handler({})

    assert result["stories"] == []


def test_list_stories_includes_archived_when_requested(seeded_story_id):
    with session_scope() as session:
        archive_story(session, seeded_story_id)

    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["list_stories"].handler({"include_archived": True})

    assert [story["id"] for story in result["stories"]] == [seeded_story_id]


def test_update_story_has_no_story_id_parameter_and_acts_on_open_story(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["update_story"].handler({"story_brief": "An updated story brief"})

    assert result["title"] == "Seed Story"
    assert result["story_brief"] == "An updated story brief"
    assert state.current_tab is ApplicationTab.STORY


def test_update_story_generation_guidance_translates_to_generation_guideance(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    result = tools["update_story"].handler({"generation_guidance": "No profanity"})

    assert result["generation_guidance"] == "No profanity"


def test_update_story_not_found_returns_error():
    state = ApplicationState(current_story_id=999)
    tools = tools_by_name(state)

    result = tools["update_story"].handler({"title": "New Title"})

    assert result == {"error": "Story 999 not found"}


def test_update_story_with_no_open_story_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["update_story"].handler({"title": "New Title"})

    assert "No story is open" in result["error"]


def test_archive_and_unarchive_story_round_trip_on_open_story(seeded_story_id):
    state = ApplicationState(current_story_id=seeded_story_id)
    tools = tools_by_name(state)

    archived = tools["archive_story"].handler({})
    assert archived["is_archived"] is True

    unarchived = tools["unarchive_story"].handler({})
    assert unarchived["is_archived"] is False


def test_archive_story_not_found_returns_error():
    state = ApplicationState(current_story_id=999)
    tools = tools_by_name(state)

    result = tools["archive_story"].handler({})

    assert result == {"error": "Story 999 not found"}


def test_archive_story_with_no_open_story_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["archive_story"].handler({})

    assert "No story is open" in result["error"]


def test_unarchive_story_not_found_returns_error():
    state = ApplicationState(current_story_id=999)
    tools = tools_by_name(state)

    result = tools["unarchive_story"].handler({})

    assert result == {"error": "Story 999 not found"}


def test_unarchive_story_with_no_open_story_returns_clear_error():
    state = ApplicationState()
    tools = tools_by_name(state)

    result = tools["unarchive_story"].handler({})

    assert "No story is open" in result["error"]


def test_story_tools_have_no_story_id_parameter_except_open_story():
    for tool in build_story_tools(ApplicationState()):
        if tool.name == "open_story":
            continue
        assert "story_id" not in tool.schema["function"]["parameters"]["properties"]


def test_tool_schemas_declare_function_name_matching_tool_name():
    for tool in build_story_tools(ApplicationState()):
        assert tool.schema["type"] == "function"
        assert tool.schema["function"]["name"] == tool.name
