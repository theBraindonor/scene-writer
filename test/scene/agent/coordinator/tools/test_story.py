import pytest

import scene.data.database as database_module
from scene.agent.coordinator.tools.story import build_story_tools
from scene.core.story import archive_story, create_story
from scene.data.database import session_scope


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


@pytest.fixture
def seeded_story_id():
    with session_scope() as session:
        story = create_story(session, title="Seed Story", scenario="A seeded scenario")
        return story.id


def tools_by_name(default_story_id):
    return {tool.name: tool for tool in build_story_tools(default_story_id)}


def test_create_story_returns_new_story():
    tools = tools_by_name(default_story_id=999)

    result = tools["create_story"].handler({"title": "New Story", "scenario": "A new scenario"})

    assert result["title"] == "New Story"
    assert result["scenario"] == "A new scenario"
    assert result["is_archived"] is False


def test_get_story_uses_default_story_id_when_omitted(seeded_story_id):
    tools = tools_by_name(default_story_id=seeded_story_id)

    result = tools["get_story"].handler({})

    assert result["id"] == seeded_story_id
    assert result["title"] == "Seed Story"


def test_get_story_uses_explicit_story_id_when_given(seeded_story_id):
    tools = tools_by_name(default_story_id=999)

    result = tools["get_story"].handler({"story_id": seeded_story_id})

    assert result["id"] == seeded_story_id


def test_get_story_not_found_returns_error():
    tools = tools_by_name(default_story_id=999)

    result = tools["get_story"].handler({})

    assert result == {"error": "Story 999 not found"}


def test_list_stories_excludes_archived_by_default(seeded_story_id):
    with session_scope() as session:
        archive_story(session, seeded_story_id)

    tools = tools_by_name(default_story_id=seeded_story_id)

    result = tools["list_stories"].handler({})

    assert result["stories"] == []


def test_list_stories_includes_archived_when_requested(seeded_story_id):
    with session_scope() as session:
        archive_story(session, seeded_story_id)

    tools = tools_by_name(default_story_id=seeded_story_id)

    result = tools["list_stories"].handler({"include_archived": True})

    assert [story["id"] for story in result["stories"]] == [seeded_story_id]


def test_update_story_changes_only_given_fields(seeded_story_id):
    tools = tools_by_name(default_story_id=seeded_story_id)

    result = tools["update_story"].handler({"scenario": "An updated scenario"})

    assert result["title"] == "Seed Story"
    assert result["scenario"] == "An updated scenario"


def test_update_story_not_found_returns_error():
    tools = tools_by_name(default_story_id=999)

    result = tools["update_story"].handler({"title": "New Title"})

    assert result == {"error": "Story 999 not found"}


def test_archive_and_unarchive_story_round_trip(seeded_story_id):
    tools = tools_by_name(default_story_id=seeded_story_id)

    archived = tools["archive_story"].handler({})
    assert archived["is_archived"] is True

    unarchived = tools["unarchive_story"].handler({})
    assert unarchived["is_archived"] is False


def test_archive_story_not_found_returns_error():
    tools = tools_by_name(default_story_id=999)

    result = tools["archive_story"].handler({})

    assert result == {"error": "Story 999 not found"}


def test_unarchive_story_not_found_returns_error():
    tools = tools_by_name(default_story_id=999)

    result = tools["unarchive_story"].handler({})

    assert result == {"error": "Story 999 not found"}


def test_tool_schemas_declare_function_name_matching_tool_name():
    for tool in build_story_tools(default_story_id=1):
        assert tool.schema["type"] == "function"
        assert tool.schema["function"]["name"] == tool.name
