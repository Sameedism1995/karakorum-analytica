import sys
from pathlib import Path

from fastapi import FastAPI
from loguru import logger

from app.api.routes import router
from app.config import get_settings
from app.jobs.scheduler import start_scheduler

settings = get_settings()

logger.remove()
logger.add(sys.stderr, level="DEBUG" if settings.debug else "INFO")

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(router)


@app.on_event("startup")
def on_startup() -> None:
    if settings.app_env == "development":
        try:
            start_scheduler()
        except Exception as exc:
            logger.warning(f"Scheduler not started: {exc}")
