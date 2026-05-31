from datetime import datetime, timedelta

from app.processors.keyword_extractor import extract_keywords


def _title_tokens(title: str | None) -> set[str]:
    if not title:
        return set()
    stop = {"the", "a", "an", "in", "on", "at", "to", "of", "and", "for", "is", "are", "with"}
    return {w for w in title.lower().split() if len(w) > 3 and w not in stop}


def _same_date(a: datetime | None, b: datetime | None, days: int = 2) -> bool:
    if a is None or b is None:
        return True  # allow match when date unknown
    return abs((a - b).days) <= days


def _location_match(a_prov: str | None, a_city: str | None, b_prov: str | None, b_city: str | None) -> bool:
    if a_city and b_city and a_city.lower() == b_city.lower():
        return True
    if a_prov and b_prov and a_prov.lower() == b_prov.lower():
        return True
    return False


def _keyword_overlap(title_a: str | None, summary_a: str | None, title_b: str | None, summary_b: str | None) -> bool:
    kw_a = set(extract_keywords(title_a, summary_a))
    kw_b = set(extract_keywords(title_b, summary_b))
    if not kw_a or not kw_b:
        return False
    return len(kw_a & kw_b) >= 1


def _title_similarity(title_a: str | None, title_b: str | None) -> bool:
    tokens_a = _title_tokens(title_a)
    tokens_b = _title_tokens(title_b)
    if not tokens_a or not tokens_b:
        return False
    overlap = len(tokens_a & tokens_b)
    return overlap >= 2 or overlap / max(len(tokens_a), len(tokens_b)) >= 0.4


def items_match(item_a: dict, item_b: dict) -> bool:
    """Rule-based check if two raw news items describe the same incident."""
    if not _same_date(item_a.get("published_at"), item_b.get("published_at")):
        return False

    if not _location_match(
        item_a.get("province"), item_a.get("city"),
        item_b.get("province"), item_b.get("city"),
    ):
        return False

    if _keyword_overlap(
        item_a.get("title"), item_a.get("summary"),
        item_b.get("title"), item_b.get("summary"),
    ):
        return True

    return _title_similarity(item_a.get("title"), item_b.get("title"))


def group_items_into_incidents(items: list[dict]) -> list[dict]:
    """
    Group similar raw news dicts into incident groups.
    Each group: {main_title, country, province, city, event_type, items, sources, keywords}
    """
    groups: list[dict] = []

    for item in items:
        placed = False
        for group in groups:
            if any(items_match(item, existing) for existing in group["items"]):
                group["items"].append(item)
                sources = {i["source_name"] for i in group["items"]}
                group["sources"] = sorted(sources)
                all_kw: set[str] = set()
                for i in group["items"]:
                    all_kw.update(extract_keywords(i.get("title"), i.get("summary")))
                group["keywords"] = sorted(all_kw)
                placed = True
                break

        if not placed:
            kw = extract_keywords(item.get("title"), item.get("summary"))
            groups.append(
                {
                    "main_title": item.get("title") or "Untitled incident",
                    "country": item.get("country") or "Pakistan",
                    "province": item.get("province"),
                    "city": item.get("city"),
                    "event_type": _infer_event_type(kw),
                    "items": [item],
                    "sources": [item["source_name"]],
                    "keywords": kw,
                }
            )

    return groups


def _infer_event_type(keywords: list[str]) -> str | None:
    event_map = {
        "explosion": ["explosion", "blast", "ied", "grenade", "suicide attack"],
        "attack": ["attack", "firing", "target killing"],
        "security_operation": ["operation", "arrest", "ctd", "police", "security forces"],
        "protest": ["protest"],
        "abduction": ["abduction", "kidnapping"],
        "clash": ["clash", "militant", "terrorism"],
    }
    kw_set = set(keywords)
    for event_type, terms in event_map.items():
        if kw_set & set(terms):
            return event_type
    return "security_incident"
