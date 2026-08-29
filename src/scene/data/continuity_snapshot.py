from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from scene.data.base import Base


class ContinuitySnapshot(Base):
    __tablename__ = "continuity_snapshot"
    __table_args__ = (
        CheckConstraint(
            "length(trim(narrative_state)) > 0", name="ck_continuity_snapshot_narrative_state_not_blank"
        ),
        UniqueConstraint(
            "story_id", "through_scene_id", name="uq_continuity_snapshot_story_id_through_scene_id"
        ),
        Index("idx_continuity_snapshot_story_id_through_scene_id", "story_id", "through_scene_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("story.id", ondelete="CASCADE"), nullable=False)
    through_scene_id: Mapped[int] = mapped_column(ForeignKey("scene.id", ondelete="CASCADE"), nullable=False)
    narrative_state: Mapped[str] = mapped_column(String, nullable=False)
    narrative_state_reasoning: Mapped[str | None] = mapped_column(String, nullable=True)
