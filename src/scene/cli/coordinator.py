import typer

from scene.agent.config import get_llm_config
from scene.agent.role import AgentRole
from scene.cli.coordinator_app import CoordinatorApp
from scene.cli.render_app import RenderApp

app = typer.Typer(help="Chat with the scene-writer coordinating agent.")


@app.callback()
def main() -> None:
    """Chat with the scene-writer coordinating agent."""


@app.command("chat")
def chat() -> None:
    try:
        config = get_llm_config(AgentRole.COORDINATING)
    except (RuntimeError, TypeError) as error:
        typer.echo(f"Could not resolve the coordinating agent's model: {error}")
        raise typer.Exit(code=1) from error

    CoordinatorApp(config).run()


@app.command("render")
def render() -> None:
    try:
        config = get_llm_config(AgentRole.RENDERING)
    except (RuntimeError, TypeError) as error:
        typer.echo(f"Could not resolve the rendering agent's model: {error}")
        raise typer.Exit(code=1) from error

    RenderApp(config).run()
