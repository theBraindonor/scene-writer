from sqlalchemy import select
from sqlalchemy.orm import Session

from scene.data.story import Story


def create_story(session: Session, title: str, scenario: str, style_guidance: str | None = None) -> Story:
    story = Story(title=title, scenario=scenario, style_guidance=style_guidance)
    session.add(story)
    session.commit()
    session.refresh(story)
    return story


def get_story(session: Session, story_id: int) -> Story | None:
    return session.get(Story, story_id)


def list_stories(session: Session, include_archived: bool = False) -> list[Story]:
    statement = select(Story)
    if not include_archived:
        statement = statement.where(Story.is_archived == 0)
    return list(session.scalars(statement.order_by(Story.id)))


def update_story(
    session: Session,
    story_id: int,
    title: str | None = None,
    scenario: str | None = None,
    style_guidance: str | None = None,
) -> Story | None:
    story = get_story(session, story_id)
    if story is None:
        return None
    if title is not None:
        story.title = title
    if scenario is not None:
        story.scenario = scenario
    if style_guidance is not None:
        story.style_guidance = style_guidance
    session.commit()
    session.refresh(story)
    return story


def archive_story(session: Session, story_id: int) -> Story | None:
    return _set_archived(session, story_id, True)


def unarchive_story(session: Session, story_id: int) -> Story | None:
    return _set_archived(session, story_id, False)


def _set_archived(session: Session, story_id: int, archived: bool) -> Story | None:
    story = get_story(session, story_id)
    if story is None:
        return None
    story.is_archived = 1 if archived else 0
    session.commit()
    session.refresh(story)
    return story
