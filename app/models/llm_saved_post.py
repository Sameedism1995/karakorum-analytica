import json
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LlmSavedPost(Base, TimestampMixin):
    """Saved LLM newsroom outputs (SQLite/Postgres)."""

    __tablename__ = "llm_saved_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    generated_output: Mapped[str] = mapped_column(Text, nullable=False)
    source_grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    audit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def set_json_field(self, field: str, value: dict | list) -> None:
        setattr(self, field, json.dumps(value, ensure_ascii=False))

    def get_json_field(self, field: str) -> dict | list | None:
        raw = getattr(self, field, None)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
