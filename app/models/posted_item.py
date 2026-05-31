from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PostedItem(Base):
    __tablename__ = "posted_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    draft_post_id: Mapped[int] = mapped_column(ForeignKey("draft_posts.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), default="x", nullable=False)
    platform_post_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    post_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    draft_post = relationship("DraftPost", back_populates="posted_items")
