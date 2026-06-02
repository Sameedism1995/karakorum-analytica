from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Post(Base, TimestampMixin):
    """Editorial post queue for Buffer/X publishing via Buffer API."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("draft_posts.id"), nullable=True, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="drafted", nullable=False, index=True)
    post_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    headline: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    scheduled_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    graphic_content: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_flags: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    editor_notes: Mapped[list | dict | str | None] = mapped_column(JSON, nullable=True)
    publish_recommendation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    buffer_response: Mapped[dict | list | str | None] = mapped_column(JSON, nullable=True)
    sent_to_buffer_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    draft_post = relationship("DraftPost", back_populates="post")
