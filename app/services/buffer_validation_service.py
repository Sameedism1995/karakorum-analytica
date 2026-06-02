"""Pre-send validation for Buffer/X posts via Zapier."""

from __future__ import annotations

import re

from app.models.post import Post

CAUTIOUS_PHRASES = (
    "local sources claim",
    "initial reports suggest",
    "official confirmation is pending",
    "the claim could not be independently verified",
)

UNVERIFIED_MARKERS = (
    "unverified",
    "not independently verified",
    "could not be independently verified",
    "claim could not",
    "sources claim",
    "local sources",
    "initial reports",
    "official confirmation is pending",
)

ATTRIBUTION_MARKERS = (
    "report",
    "claim",
    "sources",
    "according to",
    "local media",
    "open-source",
    "eyewitness",
)

SENSITIVE_KEYWORDS = (
    "casualt",
    "killed",
    "injured",
    "dead",
    "wounded",
    "attack",
    "blast",
    "explosion",
    "firing",
    "militant",
)


def validate_post_for_buffer(post: Post) -> tuple[bool, str]:
    """Return (ok, error_message). error_message is empty when ok."""
    if post is None:
        return False, "Post not found"

    if post.status != "approved":
        return False, f"Post status must be approved (current: {post.status})"

    text = (post.post_text or "").strip()
    if not text:
        return False, "post_text must not be empty"

    if len(text) > 280:
        return False, f"post_text exceeds 280 characters ({len(text)})"

    if not (post.source_name or "").strip() and not (post.source_url or "").strip():
        return False, "source_name or source_url must be present"

    if post.graphic_content:
        return False, "graphic_content posts cannot be sent via text-only Buffer step"

    verification = (post.verification_status or "").strip().lower()
    if verification == "unverified":
        if not _contains_any(text, CAUTIOUS_PHRASES):
            return False, (
                "Unverified posts must include at least one cautious phrase: "
                '"Local sources claim", "Initial reports suggest", '
                '"Official confirmation is pending", or '
                '"The claim could not be independently verified"'
            )

    grade = (post.source_grade or "").strip().upper()[:1]
    if grade in {"D", "E"}:
        if not _contains_any(text, UNVERIFIED_MARKERS):
            return False, (
                f"Source grade {grade} requires clear unverified/attribution wording "
                "(e.g. unverified, sources claim, not independently verified)"
            )

    if _contains_sensitive_topic(text) and not _has_attribution_or_caution(text):
        return False, (
            "Sensitive incident wording (casualties, attack, blast, etc.) must use "
            "attributed or cautious language"
        )

    return True, ""


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(p in lower for p in phrases)


def _contains_sensitive_topic(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in SENSITIVE_KEYWORDS)


def _has_attribution_or_caution(text: str) -> bool:
    lower = text.lower()
    if _contains_any(text, CAUTIOUS_PHRASES):
        return True
    return any(m in lower for m in ATTRIBUTION_MARKERS)


def grade_from_confidence(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 66:
        return "B"
    if score >= 33:
        return "C"
    if score >= 15:
        return "D"
    return "E"
