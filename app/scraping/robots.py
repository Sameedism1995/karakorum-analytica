"""robots.txt checks for news fetching."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from loguru import logger

DEFAULT_UA = "KarakorumAnalytica/1.0 (+https://github.com/Sameedism1995/karakorum-analytica; research)"


@lru_cache(maxsize=128)
def _load_robot_parser(origin: str, user_agent: str) -> RobotFileParser | None:
    robots_url = f"{origin}/robots.txt"
    parser = RobotFileParser()
    try:
        with httpx.Client(timeout=15.0, headers={"User-Agent": user_agent}) as client:
            response = client.get(robots_url)
            if response.status_code >= 400:
                return None
            parser.parse(response.text.splitlines())
            return parser
    except Exception as exc:
        logger.debug(f"Could not load robots.txt for {origin}: {exc}")
        return None


def allowed_to_fetch(url: str, user_agent: str = DEFAULT_UA) -> bool:
    """Return True if robots.txt permits fetching this URL (or robots unavailable)."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    origin = f"{parsed.scheme}://{parsed.netloc}"
    parser = _load_robot_parser(origin, user_agent)
    if parser is None:
        return True
    return parser.can_fetch(user_agent, url)
