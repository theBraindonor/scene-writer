from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from scene.data.base import Base


class Rendering(Base):
    __tablename__ = "rendering"
    __table_args__ = (
        CheckConstraint("is_active IN (0, 1)", name="ck_rendering_is_active_bool"),
        Index(
            "idx_rendering_one_active_per_scene",
            "scene_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey("scene.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
