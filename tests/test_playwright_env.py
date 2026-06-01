"""Tests for Playwright environment detection on servers."""

import os

import pytest

from app.config import get_settings
from app.integrations import playwright_env


def test_playwright_login_blocked_on_render(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SCWEET_AUTO_LOGIN", "true")
    get_settings.cache_clear()
    assert playwright_env.playwright_login_allowed() is False
    assert playwright_env.effective_playwright_headless(False) is True


def test_playwright_login_allowed_locally(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SCWEET_AUTO_LOGIN", "true")
    get_settings.cache_clear()
    assert playwright_env.playwright_login_allowed() is True


def test_linux_without_display_forces_headless(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SCWEET_LOGIN_HEADLESS", "false")
    get_settings.cache_clear()

    monkeypatch.setattr(playwright_env.sys, "platform", "linux")
    assert playwright_env.effective_playwright_headless(False) is True
