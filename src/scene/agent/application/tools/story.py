from typing import Any

from scene.agent.application.state import ApplicationState, ApplicationTab
from scene.agent.coordinator.loop import Tool
from scene.core.story import (
    archive_story,
    create_story,
    get_story,
    list_stories,
    unarchive_story,
    update_story,
)
from scene.data.database import session_scope
from scene.data.story import Story

_NO_OPEN_STORY = {
    "error": "No story is open. Open one with open_story, or create one with create_story."
}

_STORY_ID_REQUIRED = {"error": "story_id is required."}


def _story_dict(story: Story, state: ApplicationState) -> dict[str, Any]:
    return {
        "id": story.id,
        "title": story.title,
        "story_brief": story.story_brief,
        "style_guidance": story.style_guidance,
        "generation_guidance": story.generation_guideance,
        "is_archived": bool(story.is_archived),
        "is_open": story.id == state.current_story_id,
    }


def _not_found(story_id: int) -> dict[str, Any]:
    return {"error": f"Story {story_id} not found"}


def build_story_tools(state: ApplicationState) -> list[Tool]:
    def list_stories_handler(arguments: dict[str, Any]) -> Any:
        query = arguments.get("query")
        with session_scope() as session:
            stories = list_stories(session, include_archived=arguments.get("include_archived", False))
            if query:
                needle = query.casefold()
                stories = [story for story in stories if needle in story.title.casefold()]
            return {"stories": [_story_dict(story, state) for story in stories]}

    def open_story_handler(arguments: dict[str, Any]) -> Any:
        story_id = arguments.get("story_id")
        if story_id is None:
            return _STORY_ID_REQUIRED
        with session_scope() as session:
            story = get_story(session, story_id)
            if story is None:
                return _not_found(story_id)
            state.current_story_id = story_id
            state.current_tab = ApplicationTab.STORY
            return _story_dict(story, state)

    def create_story_handler(arguments: dict[str, Any]) -> Any:
        with session_scope() as session:
            story = create_story(
                session,
                title=arguments["title"],
                story_brief=arguments["story_brief"],
                style_guidance=arguments.get("style_guidance"),
                generation_guideance=arguments.get("generation_guidance"),
            )
            state.current_story_id = story.id
            state.current_tab = ApplicationTab.STORY
            return _story_dict(story, state)

    def update_story_handler(arguments: dict[str, Any]) -> Any:
        if state.current_story_id is None:
            return _NO_OPEN_STORY
        with session_scope() as session:
            story = update_story(
                session,
                state.current_story_id,
                title=arguments.get("title"),
                story_brief=arguments.get("story_brief"),
                style_guidance=arguments.get("style_guidance"),
                generation_guideance=arguments.get("generation_guidance"),
            )
            if story is None:
                return _not_found(state.current_story_id)
            state.current_tab = ApplicationTab.STORY
            return _story_dict(story, state)

    def archive_story_handler(arguments: dict[str, Any]) -> Any:
        if state.current_story_id is None:
            return _NO_OPEN_STORY
        with session_scope() as session:
            story = archive_story(session, state.current_story_id)
            if story is None:
                return _not_found(state.current_story_id)
            state.current_tab = ApplicationTab.STORY
            return _story_dict(story, state)

    def unarchive_story_handler(arguments: dict[str, Any]) -> Any:
        if state.current_story_id is None:
            return _NO_OPEN_STORY
        with session_scope() as session:
            story = unarchive_story(session, state.current_story_id)
            if story is None:
                return _not_found(state.current_story_id)
            state.current_tab = ApplicationTab.STORY
            return _story_dict(story, state)

    story_brief_property = {
        "type": "string",
        "description": "The story's overall situation, premise, and expected major events.",
    }
    style_guidance_property = {
        "type": "string",
        "description": "Voice, tense, point of view, tone, pacing, and similar direction.",
    }
    generation_guidance_property = {
        "type": "string",
        "description": "Generation instructions beyond style, such as content boundaries or recurring prose rules.",
    }

    return [
        Tool(
            name="list_stories",
            schema={
                "type": "function",
                "function": {
                    "name": "list_stories",
                    "description": (
                        "Find a story to open by title. Excludes archived stories unless include_archived is "
                        "true. Each result flags is_open: whether it is the story currently open in the window."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Optional text to filter titles by.",
                            },
                            "include_archived": {
                                "type": "boolean",
                                "description": "Include archived stories in the results.",
                            },
                        },
                    },
                },
            },
            handler=list_stories_handler,
        ),
        Tool(
            name="open_story",
            schema={
                "type": "function",
                "function": {
                    "name": "open_story",
                    "description": (
                        "Open a story, making it the one shown in the window: the Story tab becomes active and "
                        "the Characters/Locations tabs refresh to its data."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "story_id": {"type": "integer", "description": "The story to open, from list_stories."}
                        },
                        "required": ["story_id"],
                    },
                },
            },
            handler=open_story_handler,
        ),
        Tool(
            name="create_story",
            schema={
                "type": "function",
                "function": {
                    "name": "create_story",
                    "description": "Create a new story and open it immediately.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "The story's working title."},
                            "story_brief": story_brief_property,
                            "style_guidance": style_guidance_property,
                            "generation_guidance": generation_guidance_property,
                        },
                        "required": ["title", "story_brief"],
                    },
                },
            },
            handler=create_story_handler,
        ),
        Tool(
            name="update_story",
            schema={
                "type": "function",
                "function": {
                    "name": "update_story",
                    "description": (
                        "Update the open story's title, story brief, style guidance, and/or generation "
                        "guidance. Omitted fields are unchanged. Always acts on the open story."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "The story's working title."},
                            "story_brief": story_brief_property,
                            "style_guidance": style_guidance_property,
                            "generation_guidance": generation_guidance_property,
                        },
                    },
                },
            },
            handler=update_story_handler,
        ),
        Tool(
            name="archive_story",
            schema={
                "type": "function",
                "function": {
                    "name": "archive_story",
                    "description": "Archive the open story.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            handler=archive_story_handler,
        ),
        Tool(
            name="unarchive_story",
            schema={
                "type": "function",
                "function": {
                    "name": "unarchive_story",
                    "description": "Unarchive the open story.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            handler=unarchive_story_handler,
        ),
    ]
