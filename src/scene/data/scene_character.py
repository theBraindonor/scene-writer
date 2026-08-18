from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from scene.data.base import Base


class SceneCharacter(Base):
    __tablename__ = "scene_character"
    __table_args__ = (Index("idx_scene_character_character_id", "character_id"),)

    scene_id: Mapped[int] = mapped_column(ForeignKey("scene.id", ondelete="CASCADE"), primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("character.id", ondelete="CASCADE"), primary_key=True)
