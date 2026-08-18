from typing import Any

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


def _story_dict(story: Story) -> dict[str, Any]:
    return {
        "id": story.id,
        "title": story.title,
        "scenario": story.scenario,
        "style_guidance": story.style_guidance,
        "is_archived": bool(story.is_archived),
    }


def _not_found(story_id: int) -> dict[str, Any]:
    return {"error": f"Story {story_id} not found"}


def build_story_tools(default_story_id: int) -> list[Tool]:
    def create_story_handler(arguments: dict[str, Any]) -> Any:
        with session_scope() as session:
            story = create_story(
                session,
                title=arguments["title"],
                scenario=arguments["scenario"],
                style_guidance=arguments.get("style_guidance"),
            )
            return _story_dict(story)

    def get_story_handler(arguments: dict[str, Any]) -> Any:
        story_id = arguments.get("story_id", default_story_id)
        with session_scope() as session:
            story = get_story(session, story_id)
            return _story_dict(story) if story is not None else _not_found(story_id)

    def list_stories_handler(arguments: dict[str, Any]) -> Any:
        with session_scope() as session:
            stories = list_stories(session, include_archived=arguments.get("include_archived", False))
            return {"stories": [_story_dict(story) for story in stories]}

    def update_story_handler(arguments: dict[str, Any]) -> Any:
        story_id = arguments.get("story_id", default_story_id)
        with session_scope() as session:
            story = update_story(
                session,
                story_id,
                title=arguments.get("title"),
                scenario=arguments.get("scenario"),
                style_guidance=arguments.get("style_guidance"),
            )
            return _story_dict(story) if story is not None else _not_found(story_id)

    def archive_story_handler(arguments: dict[str, Any]) -> Any:
        story_id = arguments.get("story_id", default_story_id)
        with session_scope() as session:
            story = archive_story(session, story_id)
            return _story_dict(story) if story is not None else _not_found(story_id)

    def unarchive_story_handler(arguments: dict[str, Any]) -> Any:
        story_id = arguments.get("story_id", default_story_id)
        with session_scope() as session:
            story = unarchive_story(session, story_id)
            return _story_dict(story) if story is not None else _not_found(story_id)

    story_id_property = {
        "type": "integer",
        "description": "The story's id. Defaults to the story this conversation is about when omitted.",
    }

    return [
        Tool(
            name="create_story",
            schema={
                "type": "function",
                "function": {
                    "name": "create_story",
                    "description": "Create a new, separate story. Rarely needed inside an existing story's chat.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "The story's working title."},
                            "scenario": {
                                "type": "string",
                                "description": "The story's overall situation, premise, and expected major events.",
                            },
                            "style_guidance": {
                                "type": "string",
                                "description": "Voice, tense, point of view, tone, pacing, and similar direction.",
                            },
                        },
                        "required": ["title", "scenario"],
                    },
                },
            },
            handler=create_story_handler,
        ),
        Tool(
            name="get_story",
            schema={
                "type": "function",
                "function": {
                    "name": "get_story",
                    "description": "Get a story's current title, scenario, style guidance, and archive status.",
                    "parameters": {"type": "object", "properties": {"story_id": story_id_property}},
                },
            },
            handler=get_story_handler,
        ),
        Tool(
            name="list_stories",
            schema={
                "type": "function",
                "function": {
                    "name": "list_stories",
                    "description": "List stories. Excludes archived stories unless include_archived is true.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "include_archived": {
                                "type": "boolean",
                                "description": "Include archived stories in the results.",
                            }
                        },
                    },
                },
            },
            handler=list_stories_handler,
        ),
        Tool(
            name="update_story",
            schema={
                "type": "function",
                "function": {
                    "name": "update_story",
                    "description": "Update a story's title, scenario, and/or style guidance. Omitted fields are unchanged.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "story_id": story_id_property,
                            "title": {"type": "string", "description": "The story's working title."},
                            "scenario": {
                                "type": "string",
                                "description": "The story's overall situation, premise, and expected major events.",
                            },
                            "style_guidance": {
                                "type": "string",
                                "description": "Voice, tense, point of view, tone, pacing, and similar direction.",
                            },
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
                    "description": "Archive a story.",
                    "parameters": {"type": "object", "properties": {"story_id": story_id_property}},
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
                    "description": "Unarchive a story.",
                    "parameters": {"type": "object", "properties": {"story_id": story_id_property}},
                },
            },
            handler=unarchive_story_handler,
        ),
    ]
