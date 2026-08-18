from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from scene.data.base import Base


class Scene(Base):
    __tablename__ = "scene"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_scene_position_non_negative"),
        CheckConstraint("length(trim(description)) > 0", name="ck_scene_description_not_blank"),
        UniqueConstraint("story_id", "position", name="uq_scene_story_id_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("story.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    required_actions: Mapped[str | None] = mapped_column(String, nullable=True)
    length: Mapped[str | None] = mapped_column(String, nullable=True)
