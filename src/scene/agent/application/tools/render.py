import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from scene.agent.application.state import ApplicationState, ApplicationTab
from scene.agent.config import LLMConfig
from scene.agent.coordinator.loop import Tool
from scene.agent.rendering import earlier_scenes_rendered
from scene.core.scene import get_scene
from scene.data.database import session_scope

_NO_SELECTED_SCENE = {
    "error": "No scene is selected. Select one with select_scene, or create one with create_scene."
}
_RENDERING_NOT_CONFIGURED = {"error": "Rendering is not configured. See the Rendering panel for details."}
_EARLIER_SCENE_UNRENDERED = {"error": "An earlier scene has no active rendering yet. Render it first."}

RENDER_TIMEOUT_SECONDS = 300


@dataclass
class AgentRenderRequest:
    """Handed from the application agent's tool-call thread to the main/GUI thread to trigger
    a live, cancellable render in `RenderingColumn` — the same path a manual Render click uses
    — and carries the outcome back. `done`/`result` are filled in on the main thread and read
    back on the tool-call thread once `done` is set."""

    scene_id: int
    done: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] = field(default_factory=dict)


def _not_found(scene_id: int) -> dict[str, Any]:
    return {"error": f"Scene {scene_id} not found"}


def build_render_tools(
    state: ApplicationState,
    rendering_config: LLMConfig | None,
    request_render: Callable[[AgentRenderRequest], None],
) -> list[Tool]:
    def render_scene_handler(arguments: dict[str, Any]) -> Any:
        if state.current_scene_id is None:
            return _NO_SELECTED_SCENE
        if rendering_config is None:
            return _RENDERING_NOT_CONFIGURED

        with session_scope() as session:
            scene = get_scene(session, state.current_scene_id)
            if scene is None:
                return _not_found(state.current_scene_id)
            if not earlier_scenes_rendered(session, scene.story_id, scene.position):
                return _EARLIER_SCENE_UNRENDERED

        request = AgentRenderRequest(scene_id=state.current_scene_id)
        request_render(request)
        if not request.done.wait(timeout=RENDER_TIMEOUT_SECONDS):
            return {"error": "Rendering is taking longer than expected and is still running in the background."}

        state.current_tab = ApplicationTab.SCENES
        result = request.result
        if result.get("error") is not None:
            return {"error": f"Rendering failed: {result['error']}"}
        if result.get("cancelled"):
            return {"cancelled": True, "partial_body": result.get("body", "")}

        response: dict[str, Any] = {"scene_id": state.current_scene_id, "body": result.get("body", "")}
        continuity_error = result.get("continuity_error")
        if continuity_error is not None:
            response["continuity_warning"] = (
                f"Rendering succeeded, but updating the continuity snapshot failed: {continuity_error}"
            )
        return response

    return [
        Tool(
            name="render_scene",
            schema={
                "type": "function",
                "function": {
                    "name": "render_scene",
                    "description": (
                        "Generate a new rendering for the selected scene and make it the active version, the "
                        "same as pressing Render — live, in the Rendering column, where the writer can watch it "
                        "stream and cancel it. Returns the generated prose, or {\"cancelled\": true, "
                        "\"partial_body\": ...} if the writer cancels it. Fails if an earlier scene in the story "
                        "has no active rendering yet."
                    ),
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            handler=render_scene_handler,
        ),
    ]
