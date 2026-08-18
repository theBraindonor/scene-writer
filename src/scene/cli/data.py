import typer

from scene.core.rendering import (
    create_rendering,
    delete_rendering,
    get_rendering,
    list_renderings,
    set_active_rendering,
)
from scene.core.scene import create_scene, delete_scene, get_scene, list_scenes, update_scene
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
scene_app = typer.Typer(help="Manage scenes.")
app.add_typer(scene_app, name="scene")
rendering_app = typer.Typer(help="Manage renderings.")
app.add_typer(rendering_app, name="rendering")


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


@scene_app.command("create")
def scene_create(
    story_id: int,
    position: int,
    description: str,
    heading: str | None = None,
    required_actions: str | None = None,
) -> None:
    with session_scope() as session:
        scene = create_scene(
            session,
            story_id=story_id,
            position=position,
            description=description,
            heading=heading,
            required_actions=required_actions,
        )
        typer.echo(f"Created scene {scene.id} at position {scene.position} in story {scene.story_id}")


@scene_app.command("list")
def scene_list(story_id: int) -> None:
    with session_scope() as session:
        scenes = list_scenes(session, story_id)
        for scene in scenes:
            typer.echo(f"{scene.id}\t{scene.position}\t{scene.heading or ''}")


@scene_app.command("get")
def scene_get(scene_id: int) -> None:
    with session_scope() as session:
        scene = get_scene(session, scene_id)
        if scene is None:
            typer.echo(f"Scene {scene_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"id: {scene.id}")
        typer.echo(f"story_id: {scene.story_id}")
        typer.echo(f"position: {scene.position}")
        typer.echo(f"heading: {scene.heading}")
        typer.echo(f"description: {scene.description}")
        typer.echo(f"required_actions: {scene.required_actions}")


@scene_app.command("update")
def scene_update(
    scene_id: int,
    position: int | None = None,
    heading: str | None = None,
    description: str | None = None,
    required_actions: str | None = None,
) -> None:
    with session_scope() as session:
        scene = update_scene(
            session,
            scene_id,
            position=position,
            heading=heading,
            description=description,
            required_actions=required_actions,
        )
        if scene is None:
            typer.echo(f"Scene {scene_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"Updated scene {scene.id}")


@scene_app.command("delete")
def scene_delete(scene_id: int) -> None:
    with session_scope() as session:
        deleted = delete_scene(session, scene_id)
        if not deleted:
            typer.echo(f"Scene {scene_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"Deleted scene {scene_id}")


@rendering_app.command("create")
def rendering_create(scene_id: int, body: str) -> None:
    with session_scope() as session:
        rendering = create_rendering(session, scene_id=scene_id, body=body)
        typer.echo(f"Created rendering {rendering.id} for scene {rendering.scene_id}")


@rendering_app.command("list")
def rendering_list(scene_id: int) -> None:
    with session_scope() as session:
        renderings = list_renderings(session, scene_id)
        for rendering in renderings:
            typer.echo(f"{rendering.id}\t{bool(rendering.is_active)}")


@rendering_app.command("get")
def rendering_get(rendering_id: int) -> None:
    with session_scope() as session:
        rendering = get_rendering(session, rendering_id)
        if rendering is None:
            typer.echo(f"Rendering {rendering_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"id: {rendering.id}")
        typer.echo(f"scene_id: {rendering.scene_id}")
        typer.echo(f"is_active: {bool(rendering.is_active)}")
        typer.echo(f"body: {rendering.body}")


@rendering_app.command("set-active")
def rendering_set_active(rendering_id: int) -> None:
    with session_scope() as session:
        rendering = set_active_rendering(session, rendering_id)
        if rendering is None:
            typer.echo(f"Rendering {rendering_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"Rendering {rendering.id} is now active for scene {rendering.scene_id}")


@rendering_app.command("delete")
def rendering_delete(rendering_id: int) -> None:
    with session_scope() as session:
        deleted = delete_rendering(session, rendering_id)
        if not deleted:
            typer.echo(f"Rendering {rendering_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"Deleted rendering {rendering_id}")
