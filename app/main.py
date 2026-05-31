import sys
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes import router
from app.bootstrap import bootstrap_database
from app.config import get_settings
from app.jobs.scheduler import start_scheduler

settings = get_settings()

logger.remove()
logger.add(sys.stderr, level="DEBUG" if settings.debug else "INFO")

app = FastAPI(title=settings.app_display_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


def _run_startup_pipeline() -> None:
    """Collect, process incidents, and generate drafts once on boot."""
    from app.database import SessionLocal
    from app.services.collection_service import collect_all
    from app.services.draft_service import generate_drafts_for_incidents
    from app.services.incident_service import process_incidents

    logger.info("Startup collection pipeline running")
    db = SessionLocal()
    try:
        stats = collect_all(db)
        incident_stats = process_incidents(db)
        draft_stats = generate_drafts_for_incidents(db)
        logger.info(
            f"Startup pipeline done: collection={stats}, incidents={incident_stats}, drafts={draft_stats}"
        )
    except Exception as exc:
        logger.exception(f"Startup collection failed: {exc}")
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    try:
        bootstrap_database()
    except Exception as exc:
        logger.exception(f"Database bootstrap failed: {exc}")

    if settings.scheduler_enabled:
        try:
            start_scheduler()
        except Exception as exc:
            logger.warning(f"Scheduler not started: {exc}")

    if settings.run_collection_on_startup:
        threading.Timer(10.0, _run_startup_pipeline).start()
