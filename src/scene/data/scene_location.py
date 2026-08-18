from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from scene.data.base import Base


class SceneLocation(Base):
    __tablename__ = "scene_location"
    __table_args__ = (Index("idx_scene_location_location_id", "location_id"),)

    scene_id: Mapped[int] = mapped_column(ForeignKey("scene.id", ondelete="CASCADE"), primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("location.id", ondelete="CASCADE"), primary_key=True)
