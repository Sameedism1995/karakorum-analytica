from collections.abc import Generator

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def _build_engine(database_url: str):
    connect_args: dict = {}
    engine_kwargs: dict = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    elif database_url.startswith("postgresql"):
        if ":6543" in database_url or "pooler.supabase.com" in database_url:
            # Supavisor transaction pooler does not support prepared statements.
            connect_args["prepare_threshold"] = None
        engine_kwargs.update(
            {
                "pool_size": 5,
                "max_overflow": 10,
                "pool_recycle": 300,
            }
        )
    return create_engine(database_url, connect_args=connect_args, **engine_kwargs)


settings = get_settings()
db_url = settings.effective_database_url
engine = _build_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger.info(f"Database backend: {settings.database_backend}")


def reconfigure_engine() -> None:
    """Rebuild SQLAlchemy engine after environment/settings change."""
    global engine, SessionLocal, settings, db_url
    settings = get_settings()
    db_url = settings.effective_database_url
    engine.dispose()
    engine = _build_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info(f"Database reconfigured: {settings.database_backend}")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> dict:
    """Ping the configured database."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "ok": True,
            "backend": settings.database_backend,
            "using_supabase": settings.using_supabase,
        }
    except Exception as exc:
        return {
            "ok": False,
            "backend": settings.database_backend,
            "using_supabase": settings.using_supabase,
            "error": str(exc),
        }


def init_db() -> None:
    from app.models.source import Source  # noqa: F401
    from app.models.raw_news import RawNews  # noqa: F401
    from app.models.incident import Incident  # noqa: F401
    from app.models.draft_post import DraftPost  # noqa: F401
    from app.models.posted_item import PostedItem  # noqa: F401
    from app.models.llm_saved_post import LlmSavedPost  # noqa: F401
    from app.models.x_watch_account import XWatchAccount  # noqa: F401
    from app.models.base import Base

    Base.metadata.create_all(bind=engine)
