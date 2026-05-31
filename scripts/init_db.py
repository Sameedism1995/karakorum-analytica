#!/usr/bin/env python3
"""Initialize database and seed API sources."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import SOURCE_WEIGHT
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


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Source).count()
        if existing:
            print(f"Database already initialized ({existing} sources).")
            return
        for payload in DEFAULT_SOURCES:
            db.add(Source(**payload))
        db.commit()
        print(f"Database initialized with {len(DEFAULT_SOURCES)} sources.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
