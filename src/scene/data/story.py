from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from scene.data.base import Base


class Story(Base):
    __tablename__ = "story"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_story_title_not_blank"),
        CheckConstraint("length(trim(scenario)) > 0", name="ck_story_scenario_not_blank"),
        CheckConstraint("is_archived IN (0, 1)", name="ck_story_is_archived_bool"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    style_guidance: Mapped[str | None] = mapped_column(String, nullable=True)
    scenario: Mapped[str] = mapped_column(String, nullable=False)
    is_archived: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
