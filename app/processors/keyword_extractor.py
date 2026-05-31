from app.config import TARGET_KEYWORDS


def extract_keywords(title: str | None, summary: str | None) -> list[str]:
    """Extract matched target keywords from title and summary."""
    combined = f"{title or ''} {summary or ''}".lower()
    matched: list[str] = []
    for keyword in TARGET_KEYWORDS:
        if keyword in combined:
            matched.append(keyword)
    return sorted(set(matched))


def keywords_to_string(keywords: list[str]) -> str:
    return ", ".join(keywords)
