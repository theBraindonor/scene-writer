import typer

from scene.core.story import (
    archive_story,
    create_story,
    get_story,
    list_stories,
    unarchive_story,
    update_story,
)
from scene.data.database import session_scope

app = typer.Typer(help="Manage scene-writer's persisted data.")
story_app = typer.Typer(help="Manage stories.")
app.add_typer(story_app, name="story")


@story_app.command("create")
def create(title: str, scenario: str, style_guidance: str | None = None) -> None:
    with session_scope() as session:
        story = create_story(session, title=title, scenario=scenario, style_guidance=style_guidance)
        typer.echo(f"Created story {story.id}: {story.title}")


@story_app.command("list")
def list_command(include_archived: bool = False) -> None:
    with session_scope() as session:
        stories = list_stories(session, include_archived=include_archived)
        for story in stories:
            typer.echo(f"{story.id}\t{story.title}")


@story_app.command("get")
def get(story_id: int) -> None:
    with session_scope() as session:
        story = get_story(session, story_id)
        if story is None:
            typer.echo(f"Story {story_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"id: {story.id}")
        typer.echo(f"title: {story.title}")
        typer.echo(f"scenario: {story.scenario}")
        typer.echo(f"style_guidance: {story.style_guidance}")
        typer.echo(f"is_archived: {bool(story.is_archived)}")


@story_app.command("update")
def update(
    story_id: int,
    title: str | None = None,
    scenario: str | None = None,
    style_guidance: str | None = None,
) -> None:
    with session_scope() as session:
        story = update_story(session, story_id, title=title, scenario=scenario, style_guidance=style_guidance)
        if story is None:
            typer.echo(f"Story {story_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"Updated story {story.id}: {story.title}")


@story_app.command("archive")
def archive(story_id: int) -> None:
    with session_scope() as session:
        story = archive_story(session, story_id)
        if story is None:
            typer.echo(f"Story {story_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"Archived story {story.id}")


@story_app.command("unarchive")
def unarchive(story_id: int) -> None:
    with session_scope() as session:
        story = unarchive_story(session, story_id)
        if story is None:
            typer.echo(f"Story {story_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"Unarchived story {story.id}")
