from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models.source import Source  # noqa: F401
    from app.models.raw_news import RawNews  # noqa: F401
    from app.models.incident import Incident  # noqa: F401
    from app.models.draft_post import DraftPost  # noqa: F401
    from app.models.posted_item import PostedItem  # noqa: F401
    from app.models.base import Base

    Base.metadata.create_all(bind=engine)
