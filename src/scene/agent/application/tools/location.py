from typing import Any

from scene.agent.application.state import ApplicationState, ApplicationTab
from scene.agent.coordinator.loop import Tool
from scene.core.location import create_location, delete_location, list_locations, update_location
from scene.data.database import session_scope
from scene.data.location import Location

_NO_OPEN_STORY = {
    "error": "No story is open. Open one with open_story, or create one with create_story."
}

_LOCATION_ID_REQUIRED = {"error": "location_id is required."}


def _location_dict(location: Location) -> dict[str, Any]:
    return {
        "id": location.id,
        "story_id": location.story_id,
        "name": location.name,
        "description": location.description,
    }


def _not_found(location_id: int) -> dict[str, Any]:
    return {"error": f"Location {location_id} not found"}


def build_location_tools(state: ApplicationState) -> list[Tool]:
    def list_locations_handler(arguments: dict[str, Any]) -> Any:
        if state.current_story_id is None:
            return _NO_OPEN_STORY
        with session_scope() as session:
            locations = list_locations(session, state.current_story_id)
            return {"locations": [_location_dict(location) for location in locations]}

    def create_location_handler(arguments: dict[str, Any]) -> Any:
        if state.current_story_id is None:
            return _NO_OPEN_STORY
        with session_scope() as session:
            location = create_location(
                session,
                story_id=state.current_story_id,
                name=arguments["name"],
                description=arguments.get("description"),
            )
            state.current_location_id = location.id
            state.current_tab = ApplicationTab.LOCATIONS
            return _location_dict(location)

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
                return _not_found(location_id)
            state.current_location_id = location_id
            state.current_tab = ApplicationTab.LOCATIONS
            return _location_dict(location)

    def delete_location_handler(arguments: dict[str, Any]) -> Any:
        location_id = arguments.get("location_id")
        if location_id is None:
            return _LOCATION_ID_REQUIRED
        with session_scope() as session:
            deleted = delete_location(session, location_id)
            if not deleted:
                return _not_found(location_id)
            state.current_location_id = None
            state.current_tab = ApplicationTab.LOCATIONS
            return {"deleted": True, "id": location_id}

    location_id_property = {"type": "integer", "description": "The location's id, from list_locations."}
    name_property = {"type": "string", "description": "The location's name."}
    description_property = {"type": "string", "description": "The location's enduring physical description."}

    return [
        Tool(
            name="list_locations",
            schema={
                "type": "function",
                "function": {
                    "name": "list_locations",
                    "description": "List the open story's locations.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            handler=list_locations_handler,
        ),
        Tool(
            name="create_location",
            schema={
                "type": "function",
                "function": {
                    "name": "create_location",
                    "description": (
                        "Create a location in the open story. Switches the window to the Locations tab and "
                        "selects the new location."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {"name": name_property, "description": description_property},
                        "required": ["name"],
                    },
                },
            },
            handler=create_location_handler,
        ),
        Tool(
            name="update_location",
            schema={
                "type": "function",
                "function": {
                    "name": "update_location",
                    "description": (
                        "Update a location's name and/or description. Omitted fields are unchanged. Switches "
                        "the window to the Locations tab and selects the location."
                    ),
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
                    "description": "Delete a location. Switches the window to the Locations tab.",
                    "parameters": {
                        "type": "object",
                        "properties": {"location_id": location_id_property},
                        "required": ["location_id"],
                    },
                },
            },
            handler=delete_location_handler,
        ),
    ]
