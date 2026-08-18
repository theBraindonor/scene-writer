from typing import Any

from scene.agent.coordinator.loop import Tool
from scene.agent.coordinator.state import CoordinatorState
from scene.core.location import (
    create_location,
    delete_location,
    get_location,
    list_locations,
    update_location,
)
from scene.core.scene_location import (
    assign_location,
    list_locations_for_scene,
    list_scenes_for_location,
    unassign_location,
)
from scene.data.database import session_scope
from scene.data.location import Location
from scene.data.scene import Scene


def _location_dict(location: Location) -> dict[str, Any]:
    return {
        "id": location.id,
        "story_id": location.story_id,
        "name": location.name,
        "description": location.description,
    }


def _scene_summary(scene: Scene) -> dict[str, Any]:
    return {"id": scene.id, "story_id": scene.story_id, "position": scene.position, "heading": scene.heading}


def _location_not_found(location_id: int) -> dict[str, Any]:
    return {"error": f"Location {location_id} not found"}


_NO_CURRENT_STORY = {
    "error": "No current story. Create one with create_story, or select one with get_story(story_id=...)."
}

_LOCATION_ID_REQUIRED = {"error": "location_id is required."}
_SCENE_ID_REQUIRED = {"error": "scene_id is required."}


def _resolve_story_id(state: CoordinatorState, arguments: dict[str, Any]) -> int | None:
    story_id = arguments.get("story_id")
    return story_id if story_id is not None else state.current_story_id


def build_location_tools(state: CoordinatorState) -> list[Tool]:
    def create_location_handler(arguments: dict[str, Any]) -> Any:
        story_id = _resolve_story_id(state, arguments)
        if story_id is None:
            return _NO_CURRENT_STORY
        with session_scope() as session:
            location = create_location(
                session,
                story_id=story_id,
                name=arguments["name"],
                description=arguments.get("description"),
            )
            return _location_dict(location)

    def get_location_handler(arguments: dict[str, Any]) -> Any:
        location_id = arguments.get("location_id")
        if location_id is None:
            return _LOCATION_ID_REQUIRED
        with session_scope() as session:
            location = get_location(session, location_id)
            if location is None:
                return _location_not_found(location_id)
            return _location_dict(location)

    def list_locations_handler(arguments: dict[str, Any]) -> Any:
        story_id = _resolve_story_id(state, arguments)
        if story_id is None:
            return _NO_CURRENT_STORY
        with session_scope() as session:
            locations = list_locations(session, story_id)
            return {"locations": [_location_dict(location) for location in locations]}

    def update_location_handler(arguments: dict[str, Any]) -> Any:
        location_id = arguments.get("location_id")
        if location_id is None:
            return _LOCATION_ID_REQUIRED
        with session_scope() as session:
            location = update_location(
                session,
                location_id,
                name=arguments.get("name"),
                description=arguments.get("description"),
            )
            if location is None:
                return _location_not_found(location_id)
            return _location_dict(location)

    def delete_location_handler(arguments: dict[str, Any]) -> Any:
        location_id = arguments.get("location_id")
        if location_id is None:
            return _LOCATION_ID_REQUIRED
        with session_scope() as session:
            deleted = delete_location(session, location_id)
            if not deleted:
                return _location_not_found(location_id)
            return {"deleted": True, "id": location_id}

    def assign_location_handler(arguments: dict[str, Any]) -> Any:
        scene_id = arguments.get("scene_id")
        if scene_id is None:
            return _SCENE_ID_REQUIRED
        location_id = arguments.get("location_id")
        if location_id is None:
            return _LOCATION_ID_REQUIRED
        with session_scope() as session:
            try:
                assign_location(session, scene_id, location_id)
            except ValueError as error:
                return {"error": str(error)}
            return {"assigned": True, "scene_id": scene_id, "location_id": location_id}

    def unassign_location_handler(arguments: dict[str, Any]) -> Any:
        scene_id = arguments.get("scene_id")
        if scene_id is None:
            return _SCENE_ID_REQUIRED
        location_id = arguments.get("location_id")
        if location_id is None:
            return _LOCATION_ID_REQUIRED
        with session_scope() as session:
            unassigned = unassign_location(session, scene_id, location_id)
            if not unassigned:
                return {"error": f"Scene {scene_id} and location {location_id} are not assigned"}
            return {"assigned": False, "scene_id": scene_id, "location_id": location_id}

    def list_locations_for_scene_handler(arguments: dict[str, Any]) -> Any:
        scene_id = arguments.get("scene_id")
        if scene_id is None:
            return _SCENE_ID_REQUIRED
        with session_scope() as session:
            locations = list_locations_for_scene(session, scene_id)
            return {"locations": [_location_dict(location) for location in locations]}

    def list_scenes_for_location_handler(arguments: dict[str, Any]) -> Any:
        location_id = arguments.get("location_id")
        if location_id is None:
            return _LOCATION_ID_REQUIRED
        with session_scope() as session:
            scenes = list_scenes_for_location(session, location_id)
            return {"scenes": [_scene_summary(scene) for scene in scenes]}

    story_id_property = {
        "type": "integer",
        "description": "The story's id. Defaults to the story this conversation is about when omitted.",
    }
    location_id_property = {"type": "integer", "description": "The location's id."}
    scene_id_property = {"type": "integer", "description": "The scene's id."}
    name_property = {"type": "string", "description": "The location's name."}
    description_property = {"type": "string", "description": "The location's setting, appearance, and atmosphere."}

    return [
        Tool(
            name="create_location",
            schema={
                "type": "function",
                "function": {
                    "name": "create_location",
                    "description": "Create a new location in a story.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "story_id": story_id_property,
                            "name": name_property,
                            "description": description_property,
                        },
                        "required": ["name"],
                    },
                },
            },
            handler=create_location_handler,
        ),
        Tool(
            name="get_location",
            schema={
                "type": "function",
                "function": {
                    "name": "get_location",
                    "description": "Get a location's current name and description.",
                    "parameters": {
                        "type": "object",
                        "properties": {"location_id": location_id_property},
                        "required": ["location_id"],
                    },
                },
            },
            handler=get_location_handler,
        ),
        Tool(
            name="list_locations",
            schema={
                "type": "function",
                "function": {
                    "name": "list_locations",
                    "description": "List a story's locations.",
                    "parameters": {"type": "object", "properties": {"story_id": story_id_property}},
                },
            },
            handler=list_locations_handler,
        ),
        Tool(
            name="update_location",
            schema={
                "type": "function",
                "function": {
                    "name": "update_location",
                    "description": "Update a location's name and/or description. Omitted fields are unchanged.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location_id": location_id_property,
                            "name": name_property,
                            "description": description_property,
                        },
                        "required": ["location_id"],
                    },
                },
            },
            handler=update_location_handler,
        ),
        Tool(
            name="delete_location",
            schema={
                "type": "function",
                "function": {
                    "name": "delete_location",
                    "description": "Delete a location.",
                    "parameters": {
                        "type": "object",
                        "properties": {"location_id": location_id_property},
                        "required": ["location_id"],
                    },
                },
            },
            handler=delete_location_handler,
        ),
        Tool(
            name="assign_location",
            schema={
                "type": "function",
                "function": {
                    "name": "assign_location",
                    "description": "Add a location to a scene. The scene and location must belong to the same story.",
                    "parameters": {
                        "type": "object",
                        "properties": {"scene_id": scene_id_property, "location_id": location_id_property},
                        "required": ["scene_id", "location_id"],
                    },
                },
            },
            handler=assign_location_handler,
        ),
        Tool(
            name="unassign_location",
            schema={
                "type": "function",
                "function": {
                    "name": "unassign_location",
                    "description": "Remove a location from a scene.",
                    "parameters": {
                        "type": "object",
                        "properties": {"scene_id": scene_id_property, "location_id": location_id_property},
                        "required": ["scene_id", "location_id"],
                    },
                },
            },
            handler=unassign_location_handler,
        ),
        Tool(
            name="list_locations_for_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "list_locations_for_scene",
                    "description": "List the locations assigned to a scene.",
                    "parameters": {
                        "type": "object",
                        "properties": {"scene_id": scene_id_property},
                        "required": ["scene_id"],
                    },
                },
            },
            handler=list_locations_for_scene_handler,
        ),
        Tool(
            name="list_scenes_for_location",
            schema={
                "type": "function",
                "function": {
                    "name": "list_scenes_for_location",
                    "description": "List the scenes a location is assigned to.",
                    "parameters": {
                        "type": "object",
                        "properties": {"location_id": location_id_property},
                        "required": ["location_id"],
                    },
                },
            },
            handler=list_scenes_for_location_handler,
        ),
    ]
