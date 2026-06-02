"""Ollama local LLM HTTP client."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from app.config import get_settings


class OllamaError(Exception):
    """Raised when Ollama is unreachable or returns an error."""

    def __init__(self, message: str, *, reachable: bool = False) -> None:
        super().__init__(message)
        self.reachable = reachable


def _base_url() -> str:
    return get_settings().local_llm_base_url.rstrip("/")


def _model() -> str:
    return get_settings().local_llm_model


def is_localhost_ollama_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _is_localhost_url(url: str) -> bool:
    return is_localhost_ollama_url(url)


def local_llm_mode_active() -> bool:
    """True when Ollama should be used (explicit flag or localhost auto-detect)."""
    settings = get_settings()
    if settings.local_llm_enabled:
        return True
    if os.environ.get("RENDER"):
        return False
    return _is_localhost_url(settings.local_llm_base_url)


def probe_ollama(*, timeout: float = 3.0) -> dict[str, Any]:
    """Ping Ollama regardless of LOCAL_LLM_ENABLED."""
    settings = get_settings()
    try:
        response = httpx.get(f"{_base_url()}/api/tags", timeout=timeout)
        response.raise_for_status()
        tags = response.json().get("models") or []
        names = sorted({m.get("name", "") for m in tags if m.get("name")})
        model_base = _model().split(":")[0]
        model_available = any(
            _model() == m.get("name") or model_base == m.get("name", "").split(":")[0]
            for m in tags
        )
        return {
            "reachable": True,
            "model": settings.local_llm_model,
            "base_url": settings.local_llm_base_url,
            "models_available": names[:10],
            "model_ready": model_available,
            "error": None if model_available else f"Model {_model()} not pulled — run: ollama pull {_model()}",
        }
    except httpx.RequestError as exc:
        return {
            "reachable": False,
            "model": settings.local_llm_model,
            "base_url": settings.local_llm_base_url,
            "error": (
                f"Ollama not running at {settings.local_llm_base_url}. "
                f"Start with: ollama serve — then: ollama pull {_model()}"
            ),
        }
    except httpx.HTTPStatusError as exc:
        return {
            "reachable": False,
            "model": settings.local_llm_model,
            "base_url": settings.local_llm_base_url,
            "error": str(exc),
        }


def check_ollama() -> dict[str, Any]:
    """Ping Ollama and verify configured model is available."""
    settings = get_settings()
    active = local_llm_mode_active()
    if not active:
        return {
            "enabled": False,
            "reachable": False,
            "auto_detect": False,
            "model": settings.local_llm_model,
            "base_url": settings.local_llm_base_url,
            "error": "Local LLM disabled. Set LOCAL_LLM_ENABLED=true or run Ollama on localhost.",
        }

    auto_detect = not settings.local_llm_enabled and _is_localhost_url(settings.local_llm_base_url)
    probe = probe_ollama(timeout=8.0)
    return {
        "enabled": True,
        "auto_detect": auto_detect,
        "reachable": probe.get("reachable", False),
        "model": settings.local_llm_model,
        "base_url": settings.local_llm_base_url,
        "models_available": probe.get("models_available") or [],
        "model_ready": probe.get("model_ready", False),
        "error": probe.get("error"),
    }


def ping_generate(*, timeout: float = 15.0) -> dict[str, Any]:
    """Lightweight POST /api/generate connectivity test (stream=false)."""
    settings = get_settings()
    probe = probe_ollama(timeout=min(timeout, 8.0))
    if not probe.get("reachable"):
        return {"ok": False, "error": probe.get("error") or "Ollama unreachable"}
    if not probe.get("model_ready"):
        return {"ok": False, "error": probe.get("error") or "Model not available"}

    payload = {
        "model": _model(),
        "prompt": "Reply with exactly: ok",
        "stream": False,
        "options": {"num_predict": 8, "temperature": 0},
    }
    try:
        response = httpx.post(f"{_base_url()}/api/generate", json=payload, timeout=timeout)
        response.raise_for_status()
        body = response.json()
        logger.info(f"Ollama generate ping ok model={settings.local_llm_model}")
        return {"ok": True, "response": (body.get("response") or "")[:80]}
    except httpx.RequestError as exc:
        return {"ok": False, "error": f"Ollama /api/generate failed: {exc}"}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": f"Ollama /api/generate HTTP error: {exc.response.status_code}"}


def generate_json(system: str, user: str, *, timeout: float = 120.0) -> dict[str, Any]:
    """Call Ollama chat API and parse JSON response."""
    status = check_ollama()
    if not status.get("enabled"):
        raise OllamaError(
            status.get("error")
            or "Local LLM disabled. Set LOCAL_LLM_ENABLED=true and run: ollama serve"
        )
    if not status.get("reachable"):
        raise OllamaError(status.get("error") or "Ollama unreachable", reachable=False)
    if not status.get("model_ready"):
        raise OllamaError(status.get("error") or "Model not available", reachable=True)

    payload = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2, "num_predict": 1024},
    }
    try:
        response = httpx.post(
            f"{_base_url()}/api/chat",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        content = (response.json().get("message") or {}).get("content") or ""
        return _parse_json_content(content)
    except httpx.RequestError as exc:
        raise OllamaError(
            f"Ollama request failed at {_base_url()}: {exc}. Is `ollama serve` running?",
            reachable=False,
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise OllamaError(f"Ollama HTTP error: {exc.response.text[:200]}", reachable=True) from exc


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError as exc:
        logger.warning(f"Ollama JSON parse failed: {exc}; raw={text[:200]}")
    raise OllamaError("Local LLM returned invalid JSON", reachable=True)


def generate_text(system: str, user: str, *, timeout: float = 120.0) -> str:
    """Call Ollama chat API and return plain text."""
    status = check_ollama()
    if not status.get("enabled"):
        raise OllamaError(
            status.get("error")
            or "Local LLM disabled. Set LOCAL_LLM_ENABLED=true and run: ollama serve"
        )
    if not status.get("reachable"):
        raise OllamaError(status.get("error") or "Ollama unreachable", reachable=False)
    if not status.get("model_ready"):
        raise OllamaError(status.get("error") or "Model not available", reachable=True)

    payload = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 1024},
    }
    try:
        response = httpx.post(
            f"{_base_url()}/api/chat",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        return ((response.json().get("message") or {}).get("content") or "").strip()
    except httpx.RequestError as exc:
        raise OllamaError(
            f"Ollama request failed at {_base_url()}: {exc}. Is `ollama serve` running?",
            reachable=False,
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise OllamaError(f"Ollama HTTP error: {exc.response.text[:200]}", reachable=True) from exc
