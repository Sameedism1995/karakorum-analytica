"""Remove embedded source/grade boilerplate from tweet body text."""

from __future__ import annotations

import re

# Legacy patterns appended by template newsroom generator
_ATTRIBUTION_LINE = re.compile(
    r"\s*Based on [^.]+?\(reliability grade\s+[A-E]\)\.?\s*",
    re.IGNORECASE,
)
_FURTHER_VERIFICATION = re.compile(
    r"\s*Further verification recommended\.?\s*",
    re.IGNORECASE,
)
_UNVERIFIED_ATTRIBUTION = re.compile(
    r"\s*Unverified\.\s*Based on [^.]+?\(reliability grade\s+[A-E]\)\.?\s*",
    re.IGNORECASE,
)
_TRAILING_UNVERIFIED = re.compile(r"\s*Unverified\.\s*$", re.IGNORECASE)


def sanitize_draft_post_text(text: str) -> str:
    """Strip reliability/source footer lines from post text; metadata belongs in UI only."""
    if not text:
        return ""
    cleaned = text.strip()
    for pattern in (_UNVERIFIED_ATTRIBUTION, _ATTRIBUTION_LINE, _FURTHER_VERIFICATION):
        cleaned = pattern.sub(" ", cleaned)
    cleaned = _TRAILING_UNVERIFIED.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()
