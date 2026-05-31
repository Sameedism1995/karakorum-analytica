#!/usr/bin/env python3
"""Run the full Phase 1 pipeline once and print a summary."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loguru import logger

from app.database import SessionLocal, init_db
from app.services.collection_service import collect_all, get_recent_raw_news
from app.services.draft_service import generate_drafts_for_incidents, list_drafts
from app.services.incident_service import list_incidents, process_incidents


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        logger.info("Starting collection...")
        collection_stats = collect_all(db)

        logger.info("Processing incidents...")
        incident_stats = process_incidents(db)

        logger.info("Generating draft posts...")
        draft_stats = generate_drafts_for_incidents(db)

        raw_count = len(get_recent_raw_news(db, limit=1000))
        incidents = list_incidents(db, limit=1000)
        drafts = list_drafts(db, limit=1000)

        print("\n=== Pipeline Summary ===")
        print(f"Fetched from APIs:     {collection_stats['fetched']}")
        print(f"Saved raw news:        {collection_stats['saved']}")
        print(f"Duplicates skipped:    {collection_stats['duplicates']}")
        print(f"Filtered out:          {collection_stats['filtered_out']}")
        print(f"Incidents created:     {incident_stats['incidents_created']}")
        print(f"Incidents updated:     {incident_stats['incidents_updated']}")
        print(f"Drafts created:        {draft_stats['drafts_created']}")
        print(f"Total raw news in DB:  {raw_count}")
        print(f"Total incidents in DB: {len(incidents)}")
        print(f"Total drafts in DB:    {len(drafts)}")

        if drafts:
            print("\n--- Sample draft ---")
            print(drafts[0].post_text)
    finally:
        db.close()


if __name__ == "__main__":
    main()
