from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

from app.config import get_settings
from app.database import SessionLocal
from app.services.collection_service import collect_all
from app.services.draft_service import generate_drafts_for_incidents
from app.services.incident_service import process_incidents

scheduler = BackgroundScheduler()


def run_pipeline_job() -> None:
    """Scheduled job: collect, process incidents, generate drafts."""
    logger.info("Scheduled pipeline run starting")
    db = SessionLocal()
    try:
        collect_all(db)
        process_incidents(db)
        generate_drafts_for_incidents(db)
    finally:
        db.close()
    logger.info("Scheduled pipeline run finished")


def start_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    interval = settings.collection_interval_minutes
    scheduler.add_job(
        run_pipeline_job,
        "interval",
        minutes=interval,
        id="collection_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started (every {interval} minutes)")
    return scheduler
