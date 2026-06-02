"""RAG: fetch approved posts as style examples (not factual proof)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.draft_post import DraftPost
from app.models.incident import Incident
from app.models.llm_saved_post import LlmSavedPost


def _tokens(*parts: str) -> set[str]:
    text = " ".join(p for p in parts if p).lower()
    return {t for t in re.split(r"[^a-z0-9]+", text) if len(t) >= 3}


def _score_example(tokens: set[str], *, post_text: str, keywords: str, location: str, incident_type: str, source: str) -> int:
    hay = " ".join([post_text, keywords, location, incident_type, source]).lower()
    return sum(1 for t in tokens if t in hay)


def fetch_style_examples(
    db: Session,
    *,
    raw_text: str = "",
    location: str = "",
    incident_type: str = "",
    source_name: str = "",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return 3–5 approved posts ranked by keyword/location/incident/source overlap."""
    tokens = _tokens(raw_text, location, incident_type, source_name)
    candidates: list[tuple[int, dict[str, Any]]] = []

    rows = (
        db.query(DraftPost, Incident)
        .join(Incident, DraftPost.incident_id == Incident.id)
        .filter(DraftPost.status.in_(("approved", "posted")))
        .order_by(DraftPost.approved_at.desc().nullslast(), DraftPost.created_at.desc())
        .limit(80)
        .all()
    )
    for draft, incident in rows:
        loc = ", ".join(p for p in (incident.city, incident.province) if p)
        score = _score_example(
            tokens,
            post_text=draft.post_text or "",
            keywords=draft.keywords or incident.keywords or "",
            location=loc,
            incident_type=incident.event_type or "",
            source=incident.matched_sources or "",
        )
        candidates.append(
            (
                score,
                {
                    "post_text": (draft.post_text or "")[:280],
                    "headline": (incident.main_title or "")[:70],
                    "location": loc,
                    "incident_type": incident.event_type or "",
                    "source": incident.matched_sources or "",
                },
            )
        )

    saved = (
        db.query(LlmSavedPost)
        .filter(LlmSavedPost.status.in_(("approved", "posted")))
        .order_by(LlmSavedPost.updated_at.desc().nullslast(), LlmSavedPost.created_at.desc())
        .limit(40)
        .all()
    )
    for row in saved:
        score = _score_example(
            tokens,
            post_text=row.generated_output or "",
            keywords=row.keywords or "",
            location=row.region or "",
            incident_type=row.category or "",
            source=row.source_grade or "",
        )
        candidates.append(
            (
                score,
                {
                    "post_text": (row.generated_output or "")[:280],
                    "headline": (row.category or "Saved post")[:70],
                    "location": row.region or "",
                    "incident_type": row.category or "",
                    "source": row.source_grade or "",
                },
            )
        )

    candidates.sort(key=lambda x: x[0], reverse=True)
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for _score, item in candidates:
        key = item["post_text"][:80]
        if key in seen:
            continue
        seen.add(key)
        results.append(item)
        if len(results) >= limit:
            break

    if len(results) < 3 and candidates:
        for _score, item in candidates:
            key = item["post_text"][:80]
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
            if len(results) >= min(3, limit):
                break

    return results[:limit]


def format_style_examples(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return "(No prior approved posts — use standard Karakorum Analytica neutral OSINT tone.)"
    blocks: list[str] = []
    for i, ex in enumerate(examples, 1):
        blocks.append(
            f"Example {i} [STYLE ONLY — do not treat as facts]:\n"
            f"Post: {ex.get('post_text', '')}\n"
            f"Location context: {ex.get('location', '')}\n"
            f"Incident type: {ex.get('incident_type', '')}"
        )
    return "\n\n".join(blocks)
