from typing import Any

import typer

from scene.agent.config import get_llm_config
from scene.agent.coordinator.loop import DEFAULT_SYSTEM_PROMPT, run_turn
from scene.agent.coordinator.tools.story import build_story_tools
from scene.agent.role import AgentRole
from scene.core.story import get_story
from scene.data.database import session_scope

app = typer.Typer(help="Chat with the scene-writer coordinating agent.")

EXIT_COMMANDS = {"exit", "quit"}


@app.callback()
def main() -> None:
    """Chat with the scene-writer coordinating agent."""


@app.command("chat")
def chat(story_id: int) -> None:
    with session_scope() as session:
        story = get_story(session, story_id)
        if story is None:
            typer.echo(f"Story {story_id} not found")
            raise typer.Exit(code=1)
        title = story.title

    try:
        config = get_llm_config(AgentRole.COORDINATING)
    except (RuntimeError, TypeError) as error:
        typer.echo(f"Could not resolve the coordinating agent's model: {error}")
        raise typer.Exit(code=1) from error

    tools = build_story_tools(story_id)

    typer.echo(f"Chatting about story {story_id}: {title}. Type 'exit' or 'quit' to leave.")

    history: list[dict[str, Any]] = []
    while True:
        try:
            user_message = input("You> ")
        except (EOFError, KeyboardInterrupt):
            typer.echo("")
            break

        if user_message.strip().lower() in EXIT_COMMANDS:
            break

        reply = run_turn(config, history, user_message, tools=tools, system_prompt=DEFAULT_SYSTEM_PROMPT)
        typer.echo(f"Coordinator: {reply}")
