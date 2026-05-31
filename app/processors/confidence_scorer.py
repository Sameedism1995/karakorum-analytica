from app.config import SOURCE_NAMES, SOURCE_WEIGHT


def score_confidence(matched_sources: list[str]) -> float:
    """
    Equal source weighting:
    1 source = 33.33, 2 sources = 66.66, 3 sources = 100
    """
    unique = sorted(set(matched_sources))
    count = len(unique)
    if count <= 0:
        return 0.0
    if count >= 3:
        return 100.0
    return round(count * SOURCE_WEIGHT, 2)


def incident_status_from_score(score: float) -> str:
    """Map confidence score to incident workflow status."""
    if score < 33.34:
        return "save_only"
    if score < 66.67:
        return "needs_review"
    return "ready_for_review"


def source_breakdown(matched_sources: list[str]) -> dict[str, float]:
    """Return per-source weight for matched sources."""
    unique = sorted(set(matched_sources))
    return {name: SOURCE_WEIGHT for name in unique if name in SOURCE_NAMES}
