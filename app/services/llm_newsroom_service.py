"""LLM newsroom: generate, audit, SEO, keyword posts, and saved output CRUD."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.integrations.llm_client import (
    CASUALTY_PATTERN,
    LLMClient,
    compute_risk_score,
    detect_propaganda,
    detect_sensational,
    detect_unsupported_claims,
    has_verified_incident_text,
    normalize_grade,
    publish_status_from_score,
    slugify,
    split_keywords,
)
from app.models.llm_saved_post import LlmSavedPost
from app.schemas.llm_dashboard import (
    AuditPostRequest,
    AuditPostResponse,
    GeneratePostRequest,
    GeneratePostResponse,
    KeywordPostRequest,
    KeywordPostResponse,
    SavePostRequest,
    SeoRequest,
    SeoResponse,
)

EDITORIAL_DISCLAIMERS = [
    "Do not publish unverified claims as confirmed.",
    "Grade D/E sources require caution and attribution.",
    "Casualty figures must be attributed unless officially confirmed.",
    "The system may assist writing but does not verify facts automatically.",
]

SYSTEM_PROMPT = (
    "You are an OSINT newsroom assistant for Karakorum Analytica. "
    "Never invent facts. Use cautious, neutral language. "
    "Attribute claims to sources. Flag uncertainty."
)


def _location_label(region: str, country: str, city: str) -> str:
    parts = [p for p in (city, region, country) if p.strip()]
    return ", ".join(parts) if parts else "Pakistan"


def _attribution_line(source_type: str, grade: str) -> str:
    src = source_type.strip() or "open-source reports"
    return f"Based on {src} (reliability grade {normalize_grade(grade)})."


def _tone_prefix(tone: str) -> str:
    return {
        "neutral": "",
        "urgent": "Developing: ",
        "detailed": "Analysis — ",
        "short": "",
    }.get(tone, "")


def generate_post(payload: GeneratePostRequest) -> GeneratePostResponse:
    grade = normalize_grade(payload.source_reliability_grade)
    location = _location_label(payload.region, payload.country, payload.city_district)
    keywords = split_keywords(payload.seo_keywords) or (
        [payload.main_keyword] if payload.main_keyword else []
    )
    editorial_notes = list(EDITORIAL_DISCLAIMERS)

    if not has_verified_incident_text(payload.raw_incident_text):
        warning = (
            "Insufficient verified incident text. Outputs are framing templates only — "
            "do not publish as confirmed news."
        )
        return GeneratePostResponse(
            short_x_post=(
                f"{_tone_prefix(payload.tone)}Reports under review regarding "
                f"{payload.main_keyword or 'a security topic'} in {location}. "
                "Details unverified. #Pakistan #OSINT"
            ),
            website_post=(
                f"Karakorum Analytica is monitoring open-source reporting related to "
                f"{payload.main_keyword or 'regional security'} in {location}.\n\n"
                "No verified incident narrative was supplied. This is a placeholder draft "
                "pending source verification.\n\n"
                + _attribution_line(payload.source_type, grade)
            ),
            seo_headline=f"{payload.main_keyword or 'Pakistan security'} — monitoring update",
            meta_description=(
                f"Open-source monitoring on {payload.main_keyword or 'regional security'} "
                f"in {location}. Verification pending."
            ),
            suggested_hashtags=["#Pakistan", "#OSINT", "#KarakorumAnalytica"],
            suggested_keywords=keywords or ["Pakistan", "security", "OSINT"],
            verification_warning=warning,
            mode="template",
            editorial_notes=editorial_notes,
        )

    incident = payload.raw_incident_text.strip()
    main_kw = payload.main_keyword or keywords[0] if keywords else "security incident"
    attribution = _attribution_line(payload.source_type, grade)
    warning = None

    if grade in {"D", "E"}:
        warning = f"Source grade {grade}: require explicit attribution and avoid confirmed language."
    if CASUALTY_PATTERN.search(incident) is None and CASUALTY_PATTERN.search(incident):
        warning = (warning or "") + " Verify casualty figures before publishing."

    short_x = (
        f"{_tone_prefix(payload.tone)}"
        f"Open-source reports indicate activity related to {main_kw} in {location}. "
        f"{attribution} Further verification recommended. "
        f"{' '.join('#' + k.replace(' ', '') for k in keywords[:3] if k)}"
    ).strip()
    if payload.tone == "short":
        short_x = (
            f"{_tone_prefix(payload.tone)}Reports: {main_kw} in {location}. "
            f"Unverified. {attribution}"
        )

    website = (
        f"Open-source reporting — {payload.incident_category or 'Security update'}\n"
        f"Location: {location}\n\n"
        f"{incident}\n\n"
        f"{attribution}\n\n"
        "This summary is based on supplied source material and has not been independently "
        "verified by Karakorum Analytica."
    )

    if payload.platform == "telegram":
        short_x = f"📍 {location}\n\n{short_x}"
    elif payload.platform == "instagram":
        short_x = f"{short_x}\n\n— Karakorum Analytica | OSINT monitoring"

    seo_headline = f"{main_kw.title()} — {location} | Open-source update"
    meta = (
        f"Monitoring update on {main_kw} in {location}. "
        f"Keywords: {', '.join(keywords[:5])}. Verification advised."
    )[:160]

    hashtags = ["#Pakistan", "#OSINT", "#KarakorumAnalytica"]
    for kw in keywords[:4]:
        tag = "#" + re.sub(r"[^a-zA-Z0-9]", "", kw)
        if len(tag) > 2:
            hashtags.append(tag)

    mode = "generated"
    client = LLMClient()
    if client.is_configured:
        prompt = (
            f"Write one X/Twitter post (max 280 characters) for Karakorum Analytica OSINT.\n"
            f"Tone: {payload.tone}\n"
            f"Location: {location}\n"
            f"Main keyword: {main_kw}\n"
            f"Incident report:\n{incident}\n\n"
            f"Attribution: {attribution}\n"
            "Rules: neutral language, no unverified casualty counts, hedge claims, "
            "include 2-3 hashtags. Return ONLY the post text."
        )
        llm_result = client.complete(SYSTEM_PROMPT, prompt)
        short_x = llm_result.text.strip()[:280]
        mode = llm_result.provider

    return GeneratePostResponse(
        short_x_post=short_x[:280],
        website_post=website,
        seo_headline=seo_headline[:70],
        meta_description=meta,
        suggested_hashtags=hashtags,
        suggested_keywords=keywords or [main_kw],
        verification_warning=warning,
        mode=mode,
        editorial_notes=editorial_notes,
    )


def keyword_post(payload: KeywordPostRequest) -> KeywordPostResponse:
    topic = payload.topic_keyword.strip()
    region = payload.region.strip() or "Pakistan"
    seo_kws = split_keywords(payload.seo_keywords)
    audience = payload.target_audience.strip() or "analysts and regional observers"
    editorial_notes = list(EDITORIAL_DISCLAIMERS)

    checklist = [
        "Identify at least two independent open sources.",
        "Confirm location, time, and actors from primary reporting.",
        "Cross-check social media claims against wire services or official statements.",
        "Document source URLs, timestamps, and reliability grades.",
        "Avoid casualty numbers unless officially confirmed or multi-source corroborated.",
    ]

    caution = (
        "Karakorum Analytica: This material is for monitoring purposes. "
        "Do not treat keyword-only drafts as verified news."
    )

    if has_verified_incident_text(payload.verified_incident_text):
        incident = payload.verified_incident_text.strip()
        headlines = [
            f"{topic.title()} — open-source update ({region})",
            f"Monitoring {topic} in {region}: reports under review",
            f"{topic.title()}: multi-source check recommended",
            f"Regional security watch — {topic} ({region})",
            f"{topic.title()} | Verification checklist for {audience}",
        ]
        short_posts = [
            f"Open-source activity noted on {topic} in {region}. Verification ongoing. #OSINT",
            f"Monitoring {topic}. Sources being cross-checked. Do not repost as confirmed.",
            f"{region}: reports linked to {topic}. Awaiting corroboration.",
        ]
        full_update = (
            f"Topic: {topic}\nRegion: {region}\nAudience: {audience}\n\n"
            f"{incident}\n\n"
            f"{caution}\n\n"
            "Source verification checklist:\n"
            + "\n".join(f"- {item}" for item in checklist)
        )
        mode = "generated"
    else:
        headlines = [
            f"How to monitor {topic} using open sources",
            f"{topic.title()} — verification framework ({region})",
            f"OSINT checklist: {topic} in {region}",
            f"What to verify before reporting on {topic}",
            f"{topic.title()}: suggested search and source map",
        ]
        short_posts = [
            f"Template: Monitoring {topic} in {region}. No verified incident supplied. #OSINT",
            f"Use this checklist before posting about {topic}. Karakorum Analytica.",
            f"{topic} — search terms and source tiers (template only, not news).",
        ]
        full_update = (
            f"TOPIC MONITORING TEMPLATE — NOT A NEWS REPORT\n\n"
            f"Topic keyword: {topic}\n"
            f"Region: {region}\n"
            f"Target audience: {audience}\n"
            f"Time sensitivity: {payload.time_sensitivity}\n\n"
            "No verified incident text was provided. The following is an explainer and "
            "verification framework only.\n\n"
            "Suggested search terms:\n"
            f"- \"{topic}\" AND {region}\n"
            f"- \"{topic}\" AND (attack OR security OR border)\n\n"
            "Source verification checklist:\n"
            + "\n".join(f"- {item}" for item in checklist)
            + f"\n\n{caution}"
        )
        mode = "template"
        editorial_notes.append(
            "Keyword-only input: outputs are templates/checklists, not confirmed incident reports."
        )

    hashtags = ["#Pakistan", "#OSINT", "#KarakorumAnalytica"]
    for kw in ([topic] + seo_kws)[:4]:
        tag = "#" + re.sub(r"[^a-zA-Z0-9]", "", kw)
        if len(tag) > 2:
            hashtags.append(tag)

    return KeywordPostResponse(
        headline_options=headlines,
        short_posts=short_posts,
        full_news_update=full_update,
        hashtags=hashtags,
        recommended_caution_line=caution,
        source_verification_checklist=checklist,
        mode=mode,
        editorial_notes=editorial_notes,
    )


def audit_post(payload: AuditPostRequest) -> AuditPostResponse:
    draft = payload.draft_post.strip()
    source_info = payload.source_information.strip()
    raw_report = payload.raw_report_text.strip()

    grade_match = re.search(r"\bgrade\s*([A-E])\b", source_info, re.IGNORECASE)
    grade = normalize_grade(grade_match.group(1) if grade_match else "C")

    unsupported = detect_unsupported_claims(draft, source_info, raw_report)
    sensational = detect_sensational(draft)
    propaganda = detect_propaganda(draft)
    legal_risks: list[str] = []

    if CASUALTY_PATTERN.search(draft):
        legal_risks.append("Casualty figures require attribution to named sources or official confirmation.")
    if re.search(r"\b(named|identifies?)\s+\w+\s+(as|involved)\b", draft, re.IGNORECASE):
        legal_risks.append("Naming individuals may carry legal and safety risks — verify necessity.")
    if grade in {"D", "E"}:
        legal_risks.append(f"Grade {grade} source — use hedged language and explicit attribution.")

    risk_score = compute_risk_score(draft, grade, unsupported, sensational, propaganda)
    status_key, status_label = publish_status_from_score(risk_score)

    safer = draft
    for word in sensational:
        safer = re.sub(re.escape(word), "reported", safer, flags=re.IGNORECASE)
    safer = re.sub(r"\bconfirmed\b", "reported", safer, flags=re.IGNORECASE)
    safer = re.sub(r"\bverified\b", "according to supplied sources", safer, flags=re.IGNORECASE)
    if grade in {"D", "E"} and "according to" not in safer.lower():
        safer = f"According to open-source reporting (grade {grade}): {safer}"

    return AuditPostResponse(
        risk_score=risk_score,
        source_reliability_grade=grade,
        unsupported_claims=unsupported,
        sensational_wording=sensational,
        propaganda_wording=propaganda,
        legal_safety_risk=legal_risks,
        safer_rewritten_version=safer.strip(),
        publish_status=status_key,  # type: ignore[arg-type]
        publish_status_label=status_label,
        editorial_notes=list(EDITORIAL_DISCLAIMERS),
    )


def seo_assist(payload: SeoRequest) -> SeoResponse:
    base_text = (payload.incident_summary or payload.article_draft).strip()
    main_kw = payload.main_keyword.strip() or "Pakistan security"
    secondary = split_keywords(payload.secondary_keywords)

    title = f"{main_kw.title()} — Open-source monitoring update"
    if base_text:
        first_sentence = re.split(r"[.!?]\s+", base_text)[0][:90]
        title = f"{main_kw.title()}: {first_sentence}"[:70]

    slug = slugify(f"{main_kw}-{secondary[0] if secondary else 'update'}")
    meta = (
        f"Karakorum Analytica monitoring update on {main_kw}. "
        f"{', '.join(secondary[:3])}. Verification advised."
    )[:160]

    tags = list(dict.fromkeys([main_kw, *secondary, "Pakistan", "OSINT", "security"]))
    categories = ["Conflict monitoring", "Pakistan", "OSINT"]
    if "balochistan" in main_kw.lower() or any("balochistan" in s.lower() for s in secondary):
        categories.append("Balochistan")
    if "kp" in main_kw.lower() or "khyber" in main_kw.lower():
        categories.append("Khyber Pakhtunkhwa")

    summary = (
        base_text[:300] + "…"
        if len(base_text) > 300
        else base_text or f"Monitoring summary for {main_kw}. Awaiting verified incident details."
    )
    caption = (
        f"{main_kw} — {summary[:180]}… "
        "Source verification recommended. #Pakistan #OSINT #KarakorumAnalytica"
    )

    return SeoResponse(
        seo_title=title,
        url_slug=slug,
        meta_description=meta,
        article_tags=tags[:12],
        internal_categories=categories,
        search_friendly_summary=summary,
        social_media_caption=caption[:280],
        editorial_notes=list(EDITORIAL_DISCLAIMERS),
    )


def _serialize_json_field(value: dict | str) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _deserialize_json_field(value: str) -> dict | str:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def saved_post_to_dict(record: LlmSavedPost) -> dict:
    return {
        "id": record.id,
        "content_type": record.content_type,
        "raw_input": _deserialize_json_field(record.raw_input),
        "generated_output": _deserialize_json_field(record.generated_output),
        "source_grade": record.source_grade,
        "keywords": record.keywords,
        "seo_keywords": record.seo_keywords,
        "region": record.region,
        "category": record.category,
        "audit_score": record.audit_score,
        "status": record.status,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def list_saved_posts(db: Session, limit: int = 100) -> list[dict]:
    rows = (
        db.query(LlmSavedPost)
        .order_by(LlmSavedPost.created_at.desc())
        .limit(limit)
        .all()
    )
    return [saved_post_to_dict(r) for r in rows]


def save_post(db: Session, payload: SavePostRequest) -> dict:
    record = LlmSavedPost(
        content_type=payload.content_type,
        raw_input=_serialize_json_field(payload.raw_input),
        generated_output=_serialize_json_field(payload.generated_output),
        source_grade=payload.source_grade,
        keywords=payload.keywords,
        seo_keywords=payload.seo_keywords,
        region=payload.region,
        category=payload.category,
        audit_score=payload.audit_score,
        status=payload.status,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return saved_post_to_dict(record)


def update_post_status(db: Session, post_id: int, status: str) -> dict | None:
    record = db.query(LlmSavedPost).filter(LlmSavedPost.id == post_id).first()
    if not record:
        return None
    record.status = status
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return saved_post_to_dict(record)


def delete_saved_post(db: Session, post_id: int) -> bool:
    record = db.query(LlmSavedPost).filter(LlmSavedPost.id == post_id).first()
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True
