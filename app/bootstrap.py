"""Database initialization and source seeding."""

from __future__ import annotations

from loguru import logger

from app.config import SOURCE_WEIGHT, get_settings
from app.database import SessionLocal, init_db
from app.models.source import Source

DEFAULT_SOURCES = [
    {
        "name": "GDELT",
        "api_url": "https://api.gdeltproject.org/api/v2/doc/doc",
        "weight": SOURCE_WEIGHT,
        "is_active": True,
    },
    {
        "name": "ReliefWeb",
        "api_url": "https://api.reliefweb.int/v2/reports",
        "weight": SOURCE_WEIGHT,
        "is_active": True,
    },
    {
        "name": "ACLED",
        "api_url": "https://acleddata.com/api/acled/read",
        "weight": SOURCE_WEIGHT,
        "is_active": True,
    },
]


def bootstrap_database() -> None:
    """Create tables and seed default API sources if empty."""
    settings = get_settings()
    logger.info(f"Bootstrapping database ({settings.database_backend})")
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Source).count()
        if existing:
            logger.info(f"Database already initialized ({existing} sources)")
            return
        for payload in DEFAULT_SOURCES:
            db.add(Source(**payload))
        db.commit()
        logger.info(f"Seeded {len(DEFAULT_SOURCES)} API sources")
    finally:
        db.close()
