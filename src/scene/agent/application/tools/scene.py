from typing import Any

from sqlalchemy.orm import Session

from scene.agent.application.state import ApplicationState, ApplicationTab
from scene.agent.coordinator.loop import Tool
from scene.core.scene import create_scene, delete_scene, get_scene, list_scenes, update_scene
from scene.core.scene_character import assign_character, list_characters_for_scene, unassign_character
from scene.core.scene_location import assign_location, list_locations_for_scene, unassign_location
from scene.data.database import session_scope
from scene.data.scene import Scene

_NO_OPEN_STORY = {
    "error": "No story is open. Open one with open_story, or create one with create_story."
}

_NO_SELECTED_SCENE = {
    "error": "No scene is selected. Select one with select_scene, or create one with create_scene."
}

_SCENE_ID_REQUIRED = {"error": "scene_id is required."}
_CHARACTER_ID_REQUIRED = {"error": "character_id is required."}
_LOCATION_ID_REQUIRED = {"error": "location_id is required."}


def _not_found(scene_id: int) -> dict[str, Any]:
    return {"error": f"Scene {scene_id} not found"}


def _scene_dict(session: Session, scene: Scene, state: ApplicationState) -> dict[str, Any]:
    return {
        "id": scene.id,
        "position": scene.position,
        "heading": scene.heading,
        "brief": scene.brief,
        "required_actions": scene.required_actions,
        "pov_character_id": scene.pov_character_id,
        "desired_outcome": scene.desired_outcome,
        "target_length": scene.target_length,
        "characters": [
            {"id": character.id, "name": character.name}
            for character in list_characters_for_scene(session, scene.id)
        ],
        "locations": [
            {"id": location.id, "name": location.name} for location in list_locations_for_scene(session, scene.id)
        ],
        "is_selected": scene.id == state.current_scene_id,
    }


def build_scene_tools(state: ApplicationState) -> list[Tool]:
    def list_scenes_handler(arguments: dict[str, Any]) -> Any:
        if state.current_story_id is None:
            return _NO_OPEN_STORY
        with session_scope() as session:
            scenes = list_scenes(session, state.current_story_id)
            return {"scenes": [_scene_dict(session, scene, state) for scene in scenes]}

    def select_scene_handler(arguments: dict[str, Any]) -> Any:
        if state.current_story_id is None:
            return _NO_OPEN_STORY
        scene_id = arguments.get("scene_id")
        if scene_id is None:
            return _SCENE_ID_REQUIRED
        with session_scope() as session:
            scene = get_scene(session, scene_id)
            if scene is None:
                return _not_found(scene_id)
            if scene.story_id != state.current_story_id:
                return {"error": f"Scene {scene_id} does not belong to the open story."}
            state.current_scene_id = scene_id
            state.current_tab = ApplicationTab.SCENES
            return _scene_dict(session, scene, state)

    def create_scene_handler(arguments: dict[str, Any]) -> Any:
        if state.current_story_id is None:
            return _NO_OPEN_STORY
        with session_scope() as session:
            position = arguments.get("position")
            if position is None:
                position = len(list_scenes(session, state.current_story_id))
            try:
                scene = create_scene(
                    session,
                    story_id=state.current_story_id,
                    position=position,
                    brief=arguments["brief"],
                    heading=arguments.get("heading"),
                    required_actions=arguments.get("required_actions"),
                    target_length=arguments.get("target_length"),
                    desired_outcome=arguments.get("desired_outcome"),
                    pov_character_id=arguments.get("pov_character_id"),
                )
            except ValueError as error:
                return {"error": str(error)}
            state.current_scene_id = scene.id
            state.current_tab = ApplicationTab.SCENES
            return _scene_dict(session, scene, state)

    def update_scene_handler(arguments: dict[str, Any]) -> Any:
        if state.current_scene_id is None:
            return _NO_SELECTED_SCENE
        with session_scope() as session:
            try:
                scene = update_scene(
                    session,
                    state.current_scene_id,
                    position=arguments.get("position"),
                    heading=arguments.get("heading"),
                    brief=arguments.get("brief"),
                    required_actions=arguments.get("required_actions"),
                    target_length=arguments.get("target_length"),
                    desired_outcome=arguments.get("desired_outcome"),
                    pov_character_id=arguments.get("pov_character_id"),
                )
            except ValueError as error:
                return {"error": str(error)}
            if scene is None:
                return _not_found(state.current_scene_id)
            state.current_tab = ApplicationTab.SCENES
            return _scene_dict(session, scene, state)

    def delete_scene_handler(arguments: dict[str, Any]) -> Any:
        if state.current_scene_id is None:
            return _NO_SELECTED_SCENE
        scene_id = state.current_scene_id
        with session_scope() as session:
            deleted = delete_scene(session, scene_id)
            if not deleted:
                return _not_found(scene_id)
            state.current_scene_id = None
            state.current_tab = ApplicationTab.SCENES
            return {"deleted": True, "id": scene_id}

    def assign_character_to_scene_handler(arguments: dict[str, Any]) -> Any:
        if state.current_scene_id is None:
            return _NO_SELECTED_SCENE
        character_id = arguments.get("character_id")
        if character_id is None:
            return _CHARACTER_ID_REQUIRED
        with session_scope() as session:
            already_assigned = any(
                character.id == character_id for character in list_characters_for_scene(session, state.current_scene_id)
            )
            if not already_assigned:
                try:
                    assign_character(session, state.current_scene_id, character_id)
                except ValueError as error:
                    return {"error": str(error)}
            state.current_tab = ApplicationTab.SCENES
            scene = get_scene(session, state.current_scene_id)
            return _scene_dict(session, scene, state)

    def unassign_character_from_scene_handler(arguments: dict[str, Any]) -> Any:
        if state.current_scene_id is None:
            return _NO_SELECTED_SCENE
        character_id = arguments.get("character_id")
        if character_id is None:
            return _CHARACTER_ID_REQUIRED
        with session_scope() as session:
            unassign_character(session, state.current_scene_id, character_id)
            state.current_tab = ApplicationTab.SCENES
            scene = get_scene(session, state.current_scene_id)
            return _scene_dict(session, scene, state)

    def assign_location_to_scene_handler(arguments: dict[str, Any]) -> Any:
        if state.current_scene_id is None:
            return _NO_SELECTED_SCENE
        location_id = arguments.get("location_id")
        if location_id is None:
            return _LOCATION_ID_REQUIRED
        with session_scope() as session:
            already_assigned = any(
                location.id == location_id for location in list_locations_for_scene(session, state.current_scene_id)
            )
            if not already_assigned:
                try:
                    assign_location(session, state.current_scene_id, location_id)
                except ValueError as error:
                    return {"error": str(error)}
            state.current_tab = ApplicationTab.SCENES
            scene = get_scene(session, state.current_scene_id)
            return _scene_dict(session, scene, state)

    def unassign_location_from_scene_handler(arguments: dict[str, Any]) -> Any:
        if state.current_scene_id is None:
            return _NO_SELECTED_SCENE
        location_id = arguments.get("location_id")
        if location_id is None:
            return _LOCATION_ID_REQUIRED
        with session_scope() as session:
            unassign_location(session, state.current_scene_id, location_id)
            state.current_tab = ApplicationTab.SCENES
            scene = get_scene(session, state.current_scene_id)
            return _scene_dict(session, scene, state)

    scene_id_property = {"type": "integer", "description": "The scene's id, from list_scenes."}
    position_property = {
        "type": "integer",
        "description": "The scene's order within the story, zero-based.",
    }
    heading_property = {"type": "string", "description": "A short label for the scene."}
    brief_property = {
        "type": "string",
        "description": "The scene's setting, characters, goals, and constraints.",
    }
    required_actions_property = {
        "type": "string",
        "description": "Plot beats or actions that must occur during the scene.",
    }
    target_length_property = {"type": "string", "description": "Guidance on the scene's target length."}
    desired_outcome_property = {
        "type": "string",
        "description": "The desired state, decision, revelation, or complication by the end of the scene.",
    }
    pov_character_id_property = {
        "type": "integer",
        "description": "The character whose point of view governs the scene. Must belong to the open story.",
    }
    character_id_property = {"type": "integer", "description": "The character's id, from list_characters."}
    location_id_property = {"type": "integer", "description": "The location's id, from list_locations."}

    scene_field_properties = {
        "position": position_property,
        "heading": heading_property,
        "required_actions": required_actions_property,
        "target_length": target_length_property,
        "desired_outcome": desired_outcome_property,
        "pov_character_id": pov_character_id_property,
    }

    return [
        Tool(
            name="list_scenes",
            schema={
                "type": "function",
                "function": {
                    "name": "list_scenes",
                    "description": (
                        "List the open story's scenes, ordered by position. Each result flags is_selected and "
                        "includes its assigned characters and locations."
                    ),
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            handler=list_scenes_handler,
        ),
        Tool(
            name="select_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "select_scene",
                    "description": (
                        "Select a scene in the open story as the current one. Switches the window to the "
                        "Scenes tab. Required before update_scene, delete_scene, or the cast/location "
                        "assignment tools can act on it."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {"scene_id": scene_id_property},
                        "required": ["scene_id"],
                    },
                },
            },
            handler=select_scene_handler,
        ),
        Tool(
            name="create_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "create_scene",
                    "description": (
                        "Create a new scene in the open story and select it. position defaults to the end of "
                        "the story when omitted."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {"brief": brief_property, **scene_field_properties},
                        "required": ["brief"],
                    },
                },
            },
            handler=create_scene_handler,
        ),
        Tool(
            name="update_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "update_scene",
                    "description": (
                        "Update the selected scene's position, heading, brief, required actions, POV "
                        "character, desired outcome, and/or target length. Omitted fields are unchanged. "
                        "Always acts on the selected scene."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {"brief": brief_property, **scene_field_properties},
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
                    "description": "Delete the selected scene.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            handler=delete_scene_handler,
        ),
        Tool(
            name="assign_character_to_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "assign_character_to_scene",
                    "description": "Add a character to the selected scene's cast.",
                    "parameters": {
                        "type": "object",
                        "properties": {"character_id": character_id_property},
                        "required": ["character_id"],
                    },
                },
            },
            handler=assign_character_to_scene_handler,
        ),
        Tool(
            name="unassign_character_from_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "unassign_character_from_scene",
                    "description": "Remove a character from the selected scene's cast.",
                    "parameters": {
                        "type": "object",
                        "properties": {"character_id": character_id_property},
                        "required": ["character_id"],
                    },
                },
            },
            handler=unassign_character_from_scene_handler,
        ),
        Tool(
            name="assign_location_to_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "assign_location_to_scene",
                    "description": "Add a location to the selected scene.",
                    "parameters": {
                        "type": "object",
                        "properties": {"location_id": location_id_property},
                        "required": ["location_id"],
                    },
                },
            },
            handler=assign_location_to_scene_handler,
        ),
        Tool(
            name="unassign_location_from_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "unassign_location_from_scene",
                    "description": "Remove a location from the selected scene.",
                    "parameters": {
                        "type": "object",
                        "properties": {"location_id": location_id_property},
                        "required": ["location_id"],
                    },
                },
            },
            handler=unassign_location_from_scene_handler,
        ),
    ]
