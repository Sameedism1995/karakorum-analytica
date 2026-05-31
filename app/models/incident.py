from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    main_title: Mapped[str] = mapped_column(String(1024), nullable=False)
    country: Mapped[str] = mapped_column(String(64), default="Pakistan", nullable=False)
    province: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    matched_sources: Mapped[str | None] = mapped_column(String(256), nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="save_only", nullable=False)

    draft_posts = relationship("DraftPost", back_populates="incident")
