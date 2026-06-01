from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class XWatchAccount(Base):
    """X profiles to poll for timeline tweets (stored in raw_news via SQLAlchemy/Supabase)."""

    __tablename__ = "x_watch_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    handle: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_tweet_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_saved_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tweets_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tweets_saved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
