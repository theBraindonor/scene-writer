from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from scene.data.base import Base


class Location(Base):
    __tablename__ = "location"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_location_name_not_blank"),
        UniqueConstraint("story_id", "name", name="uq_location_story_id_name"),
        Index("idx_location_story_id", "story_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("story.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
