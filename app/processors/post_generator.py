from app.processors.keyword_extractor import keywords_to_string


def generate_draft_post(
    main_title: str,
    province: str | None,
    city: str | None,
    keywords: list[str],
    confidence_score: float,
    source_count: int,
) -> str:
    """Generate a neutral X/Twitter draft post. Never auto-posts."""
    location_parts = [p for p in [city, province] if p]
    location = ", ".join(location_parts) if location_parts else "Pakistan"

    primary_kw = _pick_display_keywords(keywords)
    kw_line = keywords_to_string(primary_kw) if primary_kw else keywords_to_string(keywords[:5])

    if confidence_score >= 66.66 and source_count >= 2:
        body = (
            f"Security incident reported in {location}.\n\n"
            f"Multiple open sources mention related activity in the area. "
            f"Official confirmation and casualty details are still being checked.\n\n"
            f"Keywords: {kw_line}"
        )
    else:
        body = (
            f"Initial reports suggest a possible security incident in {location}.\n\n"
            f"The report is currently based on limited open-source information. "
            f"Official confirmation is pending.\n\n"
            f"Keywords: {kw_line}"
        )

    return body.strip()


def _pick_display_keywords(keywords: list[str]) -> list[str]:
    priority = [
        "explosion", "blast", "attack", "clash", "operation", "protest",
        "quetta", "peshawar", "karachi", "lahore", "balochistan", "waziristan",
        "security forces", "police", "kidnapping",
    ]
    picked: list[str] = []
    kw_lower = {k.lower(): k for k in keywords}
    for p in priority:
        if p in kw_lower:
            picked.append(kw_lower[p])
        if len(picked) >= 5:
            break
    if len(picked) < 3:
        for k in keywords:
            if k not in picked:
                picked.append(k)
            if len(picked) >= 5:
                break
    return picked[:6]
