from app.config import PAKISTAN_AREAS, PROVINCE_MAP, TARGET_KEYWORDS


def _normalize(text: str) -> str:
    return text.lower().strip()


def is_pakistan_related(title: str | None, summary: str | None) -> bool:
    """Return True if text mentions Pakistan or target areas."""
    combined = _normalize(f"{title or ''} {summary or ''}")
    return any(area in combined for area in PAKISTAN_AREAS)


def detect_location(title: str | None, summary: str | None) -> tuple[str | None, str | None]:
    """Detect province and city from title and summary using keyword matching."""
    combined = _normalize(f"{title or ''} {summary or ''}")
    province = None
    city = None

    for keyword, prov in PROVINCE_MAP.items():
        if keyword in combined:
            province = prov
            if keyword in {
                "quetta", "peshawar", "gwadar", "karachi", "lahore", "islamabad",
                "waziristan", "khyber",
            }:
                city = keyword.title()
            break

    # Check city names not caught above
    cities = ["quetta", "peshawar", "gwadar", "karachi", "lahore", "islamabad", "waziristan"]
    for c in cities:
        if c in combined:
            city = c.title()
            if not province:
                province = PROVINCE_MAP.get(c)
            break

    return province, city


def filter_pakistan_item(item: dict) -> dict | None:
    """Apply Pakistan filter and enrich location fields."""
    title = item.get("title")
    summary = item.get("summary")
    if not is_pakistan_related(title, summary):
        return None

    province, city = detect_location(title, summary)
    if item.get("province"):
        province = item["province"]
    if item.get("city"):
        city = item["city"]

    item = dict(item)
    item["country"] = "Pakistan"
    item["province"] = province
    item["city"] = city
    return item


def has_security_keyword(title: str | None, summary: str | None) -> bool:
    combined = _normalize(f"{title or ''} {summary or ''}")
    return any(kw in combined for kw in TARGET_KEYWORDS)
