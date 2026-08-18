import typer

from scene.core.character import (
    create_character,
    delete_character,
    get_character,
    list_characters,
    update_character,
)
from scene.core.location import create_location, delete_location, get_location, list_locations, update_location
from scene.core.rendering import (
    create_rendering,
    delete_rendering,
    get_rendering,
    list_renderings,
    set_active_rendering,
)
from scene.core.scene import create_scene, delete_scene, get_scene, list_scenes, update_scene
from scene.core.scene_character import (
    assign_character,
    list_characters_for_scene,
    list_scenes_for_character,
    unassign_character,
)
from scene.core.scene_location import (
    assign_location,
    list_locations_for_scene,
    list_scenes_for_location,
    unassign_location,
)
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
character_app = typer.Typer(help="Manage characters.")
app.add_typer(character_app, name="character")
scene_character_app = typer.Typer(help="Manage scene cast assignments.")
app.add_typer(scene_character_app, name="scene-character")
location_app = typer.Typer(help="Manage locations.")
app.add_typer(location_app, name="location")
scene_location_app = typer.Typer(help="Manage scene location assignments.")
app.add_typer(scene_location_app, name="scene-location")


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
    length: str | None = None,
) -> None:
    with session_scope() as session:
        scene = create_scene(
            session,
            story_id=story_id,
            position=position,
            description=description,
            heading=heading,
            required_actions=required_actions,
            length=length,
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
        typer.echo(f"length: {scene.length}")


@scene_app.command("update")
def scene_update(
    scene_id: int,
    position: int | None = None,
    heading: str | None = None,
    description: str | None = None,
    required_actions: str | None = None,
    length: str | None = None,
) -> None:
    with session_scope() as session:
        scene = update_scene(
            session,
            scene_id,
            position=position,
            heading=heading,
            description=description,
            required_actions=required_actions,
            length=length,
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


@character_app.command("create")
def character_create(
    story_id: int,
    name: str,
    description: str | None = None,
    motive: str | None = None,
) -> None:
    with session_scope() as session:
        character = create_character(session, story_id=story_id, name=name, description=description, motive=motive)
        typer.echo(f"Created character {character.id}: {character.name}")


@character_app.command("list")
def character_list(story_id: int) -> None:
    with session_scope() as session:
        characters = list_characters(session, story_id)
        for character in characters:
            typer.echo(f"{character.id}\t{character.name}")


@character_app.command("get")
def character_get(character_id: int) -> None:
    with session_scope() as session:
        character = get_character(session, character_id)
        if character is None:
            typer.echo(f"Character {character_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"id: {character.id}")
        typer.echo(f"story_id: {character.story_id}")
        typer.echo(f"name: {character.name}")
        typer.echo(f"description: {character.description}")
        typer.echo(f"motive: {character.motive}")


@character_app.command("update")
def character_update(
    character_id: int,
    name: str | None = None,
    description: str | None = None,
    motive: str | None = None,
) -> None:
    with session_scope() as session:
        character = update_character(session, character_id, name=name, description=description, motive=motive)
        if character is None:
            typer.echo(f"Character {character_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"Updated character {character.id}")


@character_app.command("delete")
def character_delete(character_id: int) -> None:
    with session_scope() as session:
        deleted = delete_character(session, character_id)
        if not deleted:
            typer.echo(f"Character {character_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"Deleted character {character_id}")


@scene_character_app.command("assign")
def scene_character_assign(scene_id: int, character_id: int) -> None:
    with session_scope() as session:
        try:
            assign_character(session, scene_id=scene_id, character_id=character_id)
        except ValueError as error:
            typer.echo(str(error))
            raise typer.Exit(code=1) from error
        typer.echo(f"Assigned character {character_id} to scene {scene_id}")


@scene_character_app.command("unassign")
def scene_character_unassign(scene_id: int, character_id: int) -> None:
    with session_scope() as session:
        unassigned = unassign_character(session, scene_id=scene_id, character_id=character_id)
        if not unassigned:
            typer.echo(f"Character {character_id} is not assigned to scene {scene_id}")
            raise typer.Exit(code=1)
        typer.echo(f"Unassigned character {character_id} from scene {scene_id}")


@scene_character_app.command("list-for-scene")
def scene_character_list_for_scene(scene_id: int) -> None:
    with session_scope() as session:
        characters = list_characters_for_scene(session, scene_id)
        for character in characters:
            typer.echo(f"{character.id}\t{character.name}")


@scene_character_app.command("list-for-character")
def scene_character_list_for_character(character_id: int) -> None:
    with session_scope() as session:
        scenes = list_scenes_for_character(session, character_id)
        for scene in scenes:
            typer.echo(f"{scene.id}\t{scene.position}\t{scene.heading or ''}")


@location_app.command("create")
def location_create(story_id: int, name: str, description: str | None = None) -> None:
    with session_scope() as session:
        location = create_location(session, story_id=story_id, name=name, description=description)
        typer.echo(f"Created location {location.id}: {location.name}")


@location_app.command("list")
def location_list(story_id: int) -> None:
    with session_scope() as session:
        locations = list_locations(session, story_id)
        for location in locations:
            typer.echo(f"{location.id}\t{location.name}")


@location_app.command("get")
def location_get(location_id: int) -> None:
    with session_scope() as session:
        location = get_location(session, location_id)
        if location is None:
            typer.echo(f"Location {location_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"id: {location.id}")
        typer.echo(f"story_id: {location.story_id}")
        typer.echo(f"name: {location.name}")
        typer.echo(f"description: {location.description}")


@location_app.command("update")
def location_update(location_id: int, name: str | None = None, description: str | None = None) -> None:
    with session_scope() as session:
        location = update_location(session, location_id, name=name, description=description)
        if location is None:
            typer.echo(f"Location {location_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"Updated location {location.id}")


@location_app.command("delete")
def location_delete(location_id: int) -> None:
    with session_scope() as session:
        deleted = delete_location(session, location_id)
        if not deleted:
            typer.echo(f"Location {location_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"Deleted location {location_id}")


@scene_location_app.command("assign")
def scene_location_assign(scene_id: int, location_id: int) -> None:
    with session_scope() as session:
        try:
            assign_location(session, scene_id=scene_id, location_id=location_id)
        except ValueError as error:
            typer.echo(str(error))
            raise typer.Exit(code=1) from error
        typer.echo(f"Assigned location {location_id} to scene {scene_id}")


@scene_location_app.command("unassign")
def scene_location_unassign(scene_id: int, location_id: int) -> None:
    with session_scope() as session:
        unassigned = unassign_location(session, scene_id=scene_id, location_id=location_id)
        if not unassigned:
            typer.echo(f"Location {location_id} is not assigned to scene {scene_id}")
            raise typer.Exit(code=1)
        typer.echo(f"Unassigned location {location_id} from scene {scene_id}")


@scene_location_app.command("list-for-scene")
def scene_location_list_for_scene(scene_id: int) -> None:
    with session_scope() as session:
        locations = list_locations_for_scene(session, scene_id)
        for location in locations:
            typer.echo(f"{location.id}\t{location.name}")


@scene_location_app.command("list-for-location")
def scene_location_list_for_location(location_id: int) -> None:
    with session_scope() as session:
        scenes = list_scenes_for_location(session, location_id)
        for scene in scenes:
            typer.echo(f"{scene.id}\t{scene.position}\t{scene.heading or ''}")
