"""Obtain X session cookies via username/email + password login (Playwright)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger

DEFAULT_CACHE_PATH = "data/scweet_session.json"
SESSION_TTL_HOURS = 12

USERNAME_SELECTORS = (
    'input[name="username_or_email"]',
    'input[autocomplete*="username"]',
    'input[autocomplete="username"]',
    'input[name="text"]',
    'input[data-testid="ocfEnterTextTextInput"]',
)
PASSWORD_SELECTORS = (
    'input[name="password"]',
    'input[type="password"]',
)


def _cache_path(path: str | None) -> Path:
    return Path(path or DEFAULT_CACHE_PATH)


def load_cached_session(cache_path: str | None = None) -> dict[str, Any] | None:
    path = _cache_path(cache_path)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        expires_at = payload.get("expires_at")
        if expires_at:
            exp = datetime.fromisoformat(expires_at)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= exp:
                logger.info("Cached X session expired")
                return None
        if payload.get("auth_token"):
            return payload
    except Exception as exc:
        logger.warning(f"Could not read cached X session: {exc}")
    return None


def save_cached_session(session: dict[str, Any], cache_path: str | None = None) -> None:
    path = _cache_path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    payload = {
        **session,
        "expires_at": expires.isoformat(),
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    path.chmod(0o600)


def _first_visible_locator(page, selectors: tuple[str, ...], timeout_ms: int = 5_000):
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for selector in selectors:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible():
                return locator
        page.wait_for_timeout(250)
    return None


def _wait_for_login_form(page, timeout_ms: int = 30_000) -> None:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if page.locator("input").count() >= 1:
            username = _first_visible_locator(page, USERNAME_SELECTORS, timeout_ms=500)
            if username is not None:
                return
        page.wait_for_timeout(500)
    raise RuntimeError("X login form did not load — try SCWEET_LOGIN_HEADLESS=false")


def _fill_and_submit(locator, value: str, *, wait_ms: int = 2500) -> None:
    locator.fill(value)
    locator.press("Enter")
    locator.page.wait_for_timeout(wait_ms)


def login_x_with_credentials(
    login: str,
    password: str,
    *,
    verification_handle: str | None = None,
    headless: bool = True,
    timeout_ms: int = 90_000,
) -> dict[str, str]:
    """
    Log into x.com with phone/username/email + password and return auth_token + ct0.
    Raises RuntimeError if login fails.
    """
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required for X login. "
            "Run: pip install playwright && playwright install chromium"
        ) from exc

    login = login.strip()
    verification = (verification_handle or login).strip()
    if not headless:
        timeout_ms = max(timeout_ms, 300_000)
    logger.info(f"Logging into X as {login} (Playwright headless={headless})")
    if not headless:
        logger.info("Complete any X verification in the browser window — waiting up to 5 minutes")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()
        try:
            page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=timeout_ms)
            _wait_for_login_form(page, timeout_ms=min(timeout_ms, 30_000))

            username_input = _first_visible_locator(page, USERNAME_SELECTORS, timeout_ms=10_000)
            if username_input is None:
                raise RuntimeError("Could not find X username field")

            _fill_and_submit(username_input, login)

            for _ in range(2):
                username_input = _first_visible_locator(page, USERNAME_SELECTORS, timeout_ms=2_000)
                if username_input is None:
                    break
                _fill_and_submit(username_input, verification)

            password_input = _first_visible_locator(page, PASSWORD_SELECTORS, timeout_ms=15_000)
            if password_input is None:
                try:
                    page.locator(PASSWORD_SELECTORS[0]).first.wait_for(
                        state="visible", timeout=timeout_ms
                    )
                    password_input = page.locator(PASSWORD_SELECTORS[0]).first
                except PlaywrightTimeout as exc:
                    raise RuntimeError(
                        "X password field not found — account may need verification in a visible browser "
                        "(SCWEET_LOGIN_HEADLESS=false)."
                    ) from exc

            password_input.fill(password)
            password_input.press("Enter")

            deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout_ms / 1000)
            auth_token = ""
            while datetime.now(timezone.utc) < deadline:
                cookies = {c["name"]: c["value"] for c in context.cookies()}
                auth_token = cookies.get("auth_token", "")
                if auth_token:
                    break
                if "home" in page.url or "/status" in page.url:
                    page.wait_for_timeout(1500)
                    cookies = {c["name"]: c["value"] for c in context.cookies()}
                    auth_token = cookies.get("auth_token", "")
                    if auth_token:
                        break
                page.wait_for_timeout(1500)

            cookies = {c["name"]: c["value"] for c in context.cookies()}
            auth_token = cookies.get("auth_token", "")
            ct0 = cookies.get("ct0", "")

            if not auth_token:
                raise RuntimeError(
                    "X login did not produce auth_token. Check username/password, 2FA, or "
                    "complete any verification challenge in a visible browser "
                    "(SCWEET_LOGIN_HEADLESS=false)."
                )

            logger.info("X login succeeded — session cookies captured")
            return {
                "auth_token": auth_token,
                "ct0": ct0,
                "login": login,
                "username": verification,
            }
        finally:
            browser.close()


def get_or_create_x_session(
    login: str,
    password: str,
    *,
    verification_handle: str | None = None,
    cache_path: str | None = None,
    headless: bool = True,
    force_refresh: bool = False,
) -> dict[str, str]:
    """Return cached or freshly logged-in X session cookies."""
    if not force_refresh:
        cached = load_cached_session(cache_path)
        if cached and cached.get("auth_token"):
            logger.info("Using cached X session")
            return cached

    session = login_x_with_credentials(
        login,
        password,
        verification_handle=verification_handle,
        headless=headless,
    )
    save_cached_session(session, cache_path)
    return session
