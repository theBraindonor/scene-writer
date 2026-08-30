from typing import Any

from scene.agent.application.state import ApplicationState, ApplicationTab
from scene.agent.coordinator.loop import Tool
from scene.core.character import create_character, delete_character, list_characters, update_character
from scene.data.character import Character
from scene.data.database import session_scope

_NO_OPEN_STORY = {
    "error": "No story is open. Open one with open_story, or create one with create_story."
}

_CHARACTER_ID_REQUIRED = {"error": "character_id is required."}


def _character_dict(character: Character) -> dict[str, Any]:
    return {
        "id": character.id,
        "story_id": character.story_id,
        "name": character.name,
        "description": character.description,
        "motive": character.motive,
    }


def _not_found(character_id: int) -> dict[str, Any]:
    return {"error": f"Character {character_id} not found"}


def build_character_tools(state: ApplicationState) -> list[Tool]:
    def list_characters_handler(arguments: dict[str, Any]) -> Any:
        if state.current_story_id is None:
            return _NO_OPEN_STORY
        with session_scope() as session:
            characters = list_characters(session, state.current_story_id)
            return {"characters": [_character_dict(character) for character in characters]}

    def create_character_handler(arguments: dict[str, Any]) -> Any:
        if state.current_story_id is None:
            return _NO_OPEN_STORY
        with session_scope() as session:
            character = create_character(
                session,
                story_id=state.current_story_id,
                name=arguments["name"],
                description=arguments.get("description"),
                motive=arguments.get("motive"),
            )
            state.current_character_id = character.id
            state.current_tab = ApplicationTab.CHARACTERS
            return _character_dict(character)

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
                return _not_found(character_id)
            state.current_character_id = character_id
            state.current_tab = ApplicationTab.CHARACTERS
            return _character_dict(character)

    def delete_character_handler(arguments: dict[str, Any]) -> Any:
        character_id = arguments.get("character_id")
        if character_id is None:
            return _CHARACTER_ID_REQUIRED
        with session_scope() as session:
            deleted = delete_character(session, character_id)
            if not deleted:
                return _not_found(character_id)
            state.current_character_id = None
            state.current_tab = ApplicationTab.CHARACTERS
            return {"deleted": True, "id": character_id}

    character_id_property = {"type": "integer", "description": "The character's id, from list_characters."}
    name_property = {"type": "string", "description": "The character's name."}
    description_property = {"type": "string", "description": "The character's appearance, personality, and role."}
    motive_property = {"type": "string", "description": "What the character wants; drives their actions."}

    return [
        Tool(
            name="list_characters",
            schema={
                "type": "function",
                "function": {
                    "name": "list_characters",
                    "description": "List the open story's characters.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            handler=list_characters_handler,
        ),
        Tool(
            name="create_character",
            schema={
                "type": "function",
                "function": {
                    "name": "create_character",
                    "description": (
                        "Create a character in the open story. Switches the window to the Characters tab and "
                        "selects the new character."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
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
            name="update_character",
            schema={
                "type": "function",
                "function": {
                    "name": "update_character",
                    "description": (
                        "Update a character's name, description, and/or motive. Omitted fields are unchanged. "
                        "Switches the window to the Characters tab and selects the character."
                    ),
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
                    "description": "Delete a character. Switches the window to the Characters tab.",
                    "parameters": {
                        "type": "object",
                        "properties": {"character_id": character_id_property},
                        "required": ["character_id"],
                    },
                },
            },
            handler=delete_character_handler,
        ),
    ]
