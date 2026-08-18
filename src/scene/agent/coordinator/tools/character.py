from typing import Any

from scene.agent.coordinator.loop import Tool
from scene.agent.coordinator.state import CoordinatorState
from scene.core.character import (
    create_character,
    delete_character,
    get_character,
    list_characters,
    update_character,
)
from scene.core.scene_character import (
    assign_character,
    list_characters_for_scene,
    list_scenes_for_character,
    unassign_character,
)
from scene.data.character import Character
from scene.data.database import session_scope
from scene.data.scene import Scene


def _character_dict(character: Character) -> dict[str, Any]:
    return {
        "id": character.id,
        "story_id": character.story_id,
        "name": character.name,
        "description": character.description,
        "motive": character.motive,
    }


def _scene_summary(scene: Scene) -> dict[str, Any]:
    return {"id": scene.id, "story_id": scene.story_id, "position": scene.position, "heading": scene.heading}


def _character_not_found(character_id: int) -> dict[str, Any]:
    return {"error": f"Character {character_id} not found"}


_NO_CURRENT_STORY = {
    "error": "No current story. Create one with create_story, or select one with get_story(story_id=...)."
}

_CHARACTER_ID_REQUIRED = {"error": "character_id is required."}
_SCENE_ID_REQUIRED = {"error": "scene_id is required."}


def _resolve_story_id(state: CoordinatorState, arguments: dict[str, Any]) -> int | None:
    story_id = arguments.get("story_id")
    return story_id if story_id is not None else state.current_story_id


def build_character_tools(state: CoordinatorState) -> list[Tool]:
    def create_character_handler(arguments: dict[str, Any]) -> Any:
        story_id = _resolve_story_id(state, arguments)
        if story_id is None:
            return _NO_CURRENT_STORY
        with session_scope() as session:
            character = create_character(
                session,
                story_id=story_id,
                name=arguments["name"],
                description=arguments.get("description"),
                motive=arguments.get("motive"),
            )
            return _character_dict(character)

    def get_character_handler(arguments: dict[str, Any]) -> Any:
        character_id = arguments.get("character_id")
        if character_id is None:
            return _CHARACTER_ID_REQUIRED
        with session_scope() as session:
            character = get_character(session, character_id)
            if character is None:
                return _character_not_found(character_id)
            return _character_dict(character)

    def list_characters_handler(arguments: dict[str, Any]) -> Any:
        story_id = _resolve_story_id(state, arguments)
        if story_id is None:
            return _NO_CURRENT_STORY
        with session_scope() as session:
            characters = list_characters(session, story_id)
            return {"characters": [_character_dict(character) for character in characters]}

    def update_character_handler(arguments: dict[str, Any]) -> Any:
        character_id = arguments.get("character_id")
        if character_id is None:
            return _CHARACTER_ID_REQUIRED
        with session_scope() as session:
            character = update_character(
                session,
                character_id,
                name=arguments.get("name"),
                description=arguments.get("description"),
                motive=arguments.get("motive"),
            )
            if character is None:
                return _character_not_found(character_id)
            return _character_dict(character)

    def delete_character_handler(arguments: dict[str, Any]) -> Any:
        character_id = arguments.get("character_id")
        if character_id is None:
            return _CHARACTER_ID_REQUIRED
        with session_scope() as session:
            deleted = delete_character(session, character_id)
            if not deleted:
                return _character_not_found(character_id)
            return {"deleted": True, "id": character_id}

    def assign_character_handler(arguments: dict[str, Any]) -> Any:
        scene_id = arguments.get("scene_id")
        if scene_id is None:
            return _SCENE_ID_REQUIRED
        character_id = arguments.get("character_id")
        if character_id is None:
            return _CHARACTER_ID_REQUIRED
        with session_scope() as session:
            try:
                assign_character(session, scene_id, character_id)
            except ValueError as error:
                return {"error": str(error)}
            return {"assigned": True, "scene_id": scene_id, "character_id": character_id}

    def unassign_character_handler(arguments: dict[str, Any]) -> Any:
        scene_id = arguments.get("scene_id")
        if scene_id is None:
            return _SCENE_ID_REQUIRED
        character_id = arguments.get("character_id")
        if character_id is None:
            return _CHARACTER_ID_REQUIRED
        with session_scope() as session:
            unassigned = unassign_character(session, scene_id, character_id)
            if not unassigned:
                return {"error": f"Scene {scene_id} and character {character_id} are not assigned"}
            return {"assigned": False, "scene_id": scene_id, "character_id": character_id}

    def list_characters_for_scene_handler(arguments: dict[str, Any]) -> Any:
        scene_id = arguments.get("scene_id")
        if scene_id is None:
            return _SCENE_ID_REQUIRED
        with session_scope() as session:
            characters = list_characters_for_scene(session, scene_id)
            return {"characters": [_character_dict(character) for character in characters]}

    def list_scenes_for_character_handler(arguments: dict[str, Any]) -> Any:
        character_id = arguments.get("character_id")
        if character_id is None:
            return _CHARACTER_ID_REQUIRED
        with session_scope() as session:
            scenes = list_scenes_for_character(session, character_id)
            return {"scenes": [_scene_summary(scene) for scene in scenes]}

    story_id_property = {
        "type": "integer",
        "description": "The story's id. Defaults to the story this conversation is about when omitted.",
    }
    character_id_property = {"type": "integer", "description": "The character's id."}
    scene_id_property = {"type": "integer", "description": "The scene's id."}
    name_property = {"type": "string", "description": "The character's name."}
    description_property = {"type": "string", "description": "The character's appearance, personality, and role."}
    motive_property = {"type": "string", "description": "What the character wants; drives their actions."}

    return [
        Tool(
            name="create_character",
            schema={
                "type": "function",
                "function": {
                    "name": "create_character",
                    "description": "Create a new character in a story.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "story_id": story_id_property,
                            "name": name_property,
                            "description": description_property,
                            "motive": motive_property,
                        },
                        "required": ["name"],
                    },
                },
            },
            handler=create_character_handler,
        ),
        Tool(
            name="get_character",
            schema={
                "type": "function",
                "function": {
                    "name": "get_character",
                    "description": "Get a character's current name, description, and motive.",
                    "parameters": {
                        "type": "object",
                        "properties": {"character_id": character_id_property},
                        "required": ["character_id"],
                    },
                },
            },
            handler=get_character_handler,
        ),
        Tool(
            name="list_characters",
            schema={
                "type": "function",
                "function": {
                    "name": "list_characters",
                    "description": "List a story's characters.",
                    "parameters": {"type": "object", "properties": {"story_id": story_id_property}},
                },
            },
            handler=list_characters_handler,
        ),
        Tool(
            name="update_character",
            schema={
                "type": "function",
                "function": {
                    "name": "update_character",
                    "description": "Update a character's name, description, and/or motive. Omitted fields are unchanged.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "character_id": character_id_property,
                            "name": name_property,
                            "description": description_property,
                            "motive": motive_property,
                        },
                        "required": ["character_id"],
                    },
                },
            },
            handler=update_character_handler,
        ),
        Tool(
            name="delete_character",
            schema={
                "type": "function",
                "function": {
                    "name": "delete_character",
                    "description": "Delete a character.",
                    "parameters": {
                        "type": "object",
                        "properties": {"character_id": character_id_property},
                        "required": ["character_id"],
                    },
                },
            },
            handler=delete_character_handler,
        ),
        Tool(
            name="assign_character",
            schema={
                "type": "function",
                "function": {
                    "name": "assign_character",
                    "description": "Add a character to a scene's cast. The scene and character must belong to the same story.",
                    "parameters": {
                        "type": "object",
                        "properties": {"scene_id": scene_id_property, "character_id": character_id_property},
                        "required": ["scene_id", "character_id"],
                    },
                },
            },
            handler=assign_character_handler,
        ),
        Tool(
            name="unassign_character",
            schema={
                "type": "function",
                "function": {
                    "name": "unassign_character",
                    "description": "Remove a character from a scene's cast.",
                    "parameters": {
                        "type": "object",
                        "properties": {"scene_id": scene_id_property, "character_id": character_id_property},
                        "required": ["scene_id", "character_id"],
                    },
                },
            },
            handler=unassign_character_handler,
        ),
        Tool(
            name="list_characters_for_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "list_characters_for_scene",
                    "description": "List the characters assigned to a scene.",
                    "parameters": {
                        "type": "object",
                        "properties": {"scene_id": scene_id_property},
                        "required": ["scene_id"],
                    },
                },
            },
            handler=list_characters_for_scene_handler,
        ),
        Tool(
            name="list_scenes_for_character",
            schema={
                "type": "function",
                "function": {
                    "name": "list_scenes_for_character",
                    "description": "List the scenes a character is assigned to.",
                    "parameters": {
                        "type": "object",
                        "properties": {"character_id": character_id_property},
                        "required": ["character_id"],
                    },
                },
            },
            handler=list_scenes_for_character_handler,
        ),
    ]
