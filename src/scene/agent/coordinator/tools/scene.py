from typing import Any

from scene.agent.coordinator.loop import Tool
from scene.agent.coordinator.state import CoordinatorState
from scene.core.scene import (
    create_scene,
    delete_scene,
    get_scene,
    list_scenes,
    update_scene,
)
from scene.data.database import session_scope
from scene.data.scene import Scene


def _scene_dict(scene: Scene) -> dict[str, Any]:
    return {
        "id": scene.id,
        "story_id": scene.story_id,
        "position": scene.position,
        "heading": scene.heading,
        "description": scene.description,
        "required_actions": scene.required_actions,
        "length": scene.length,
    }


def _not_found(scene_id: int) -> dict[str, Any]:
    return {"error": f"Scene {scene_id} not found"}


_NO_CURRENT_STORY = {
    "error": "No current story. Create one with create_story, or select one with get_story(story_id=...)."
}

_SCENE_ID_REQUIRED = {"error": "scene_id is required."}


def _resolve_story_id(state: CoordinatorState, arguments: dict[str, Any]) -> int | None:
    story_id = arguments.get("story_id")
    return story_id if story_id is not None else state.current_story_id


def build_scene_tools(state: CoordinatorState) -> list[Tool]:
    def create_scene_handler(arguments: dict[str, Any]) -> Any:
        story_id = _resolve_story_id(state, arguments)
        if story_id is None:
            return _NO_CURRENT_STORY
        with session_scope() as session:
            scene = create_scene(
                session,
                story_id=story_id,
                position=arguments["position"],
                description=arguments["description"],
                heading=arguments.get("heading"),
                required_actions=arguments.get("required_actions"),
                length=arguments.get("length"),
            )
            return _scene_dict(scene)

    def get_scene_handler(arguments: dict[str, Any]) -> Any:
        scene_id = arguments.get("scene_id")
        if scene_id is None:
            return _SCENE_ID_REQUIRED
        with session_scope() as session:
            scene = get_scene(session, scene_id)
            if scene is None:
                return _not_found(scene_id)
            return _scene_dict(scene)

    def list_scenes_handler(arguments: dict[str, Any]) -> Any:
        story_id = _resolve_story_id(state, arguments)
        if story_id is None:
            return _NO_CURRENT_STORY
        with session_scope() as session:
            scenes = list_scenes(session, story_id)
            return {"scenes": [_scene_dict(scene) for scene in scenes]}

    def update_scene_handler(arguments: dict[str, Any]) -> Any:
        scene_id = arguments.get("scene_id")
        if scene_id is None:
            return _SCENE_ID_REQUIRED
        with session_scope() as session:
            scene = update_scene(
                session,
                scene_id,
                position=arguments.get("position"),
                heading=arguments.get("heading"),
                description=arguments.get("description"),
                required_actions=arguments.get("required_actions"),
                length=arguments.get("length"),
            )
            if scene is None:
                return _not_found(scene_id)
            return _scene_dict(scene)

    def delete_scene_handler(arguments: dict[str, Any]) -> Any:
        scene_id = arguments.get("scene_id")
        if scene_id is None:
            return _SCENE_ID_REQUIRED
        with session_scope() as session:
            deleted = delete_scene(session, scene_id)
            if not deleted:
                return _not_found(scene_id)
            return {"deleted": True, "id": scene_id}

    story_id_property = {
        "type": "integer",
        "description": "The story's id. Defaults to the story this conversation is about when omitted.",
    }
    scene_id_property = {"type": "integer", "description": "The scene's id."}
    position_property = {
        "type": "integer",
        "description": "The scene's order within the story, zero-based.",
    }
    heading_property = {"type": "string", "description": "A short label for the scene."}
    description_property = {
        "type": "string",
        "description": "The scene's setting, characters, goals, and constraints.",
    }
    required_actions_property = {
        "type": "string",
        "description": "Plot beats or actions that must occur during the scene.",
    }
    length_property = {"type": "string", "description": "Guidance on the scene's target length."}

    return [
        Tool(
            name="create_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "create_scene",
                    "description": "Create a new scene in a story, at a given position.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "story_id": story_id_property,
                            "position": position_property,
                            "heading": heading_property,
                            "description": description_property,
                            "required_actions": required_actions_property,
                            "length": length_property,
                        },
                        "required": ["position", "description"],
                    },
                },
            },
            handler=create_scene_handler,
        ),
        Tool(
            name="get_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "get_scene",
                    "description": "Get a scene's current position, heading, description, required actions, and length.",
                    "parameters": {
                        "type": "object",
                        "properties": {"scene_id": scene_id_property},
                        "required": ["scene_id"],
                    },
                },
            },
            handler=get_scene_handler,
        ),
        Tool(
            name="list_scenes",
            schema={
                "type": "function",
                "function": {
                    "name": "list_scenes",
                    "description": "List a story's scenes, ordered by position.",
                    "parameters": {"type": "object", "properties": {"story_id": story_id_property}},
                },
            },
            handler=list_scenes_handler,
        ),
        Tool(
            name="update_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "update_scene",
                    "description": (
                        "Update a scene's position, heading, description, required actions, and/or length. "
                        "Omitted fields are unchanged."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scene_id": scene_id_property,
                            "position": position_property,
                            "heading": heading_property,
                            "description": description_property,
                            "required_actions": required_actions_property,
                            "length": length_property,
                        },
                        "required": ["scene_id"],
                    },
                },
            },
            handler=update_scene_handler,
        ),
        Tool(
            name="delete_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "delete_scene",
                    "description": "Delete a scene.",
                    "parameters": {
                        "type": "object",
                        "properties": {"scene_id": scene_id_property},
                        "required": ["scene_id"],
                    },
                },
            },
            handler=delete_scene_handler,
        ),
    ]
