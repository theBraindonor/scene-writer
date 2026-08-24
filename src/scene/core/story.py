from sqlalchemy import select
from sqlalchemy.orm import Session

from scene.data.story import Story


def create_story(
    session: Session,
    title: str,
    story_brief: str,
    style_guidance: str | None = None,
    generation_guideance: str | None = None,
) -> Story:
    story = Story(
        title=title,
        story_brief=story_brief,
        style_guidance=style_guidance,
        generation_guideance=generation_guideance,
    )
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
    story_brief: str | None = None,
    style_guidance: str | None = None,
    generation_guideance: str | None = None,
) -> Story | None:
    story = get_story(session, story_id)
    if story is None:
        return None
    if title is not None:
        story.title = title
    if story_brief is not None:
        story.story_brief = story_brief
    if style_guidance is not None:
        story.style_guidance = style_guidance
    if generation_guideance is not None:
        story.generation_guideance = generation_guideance
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
