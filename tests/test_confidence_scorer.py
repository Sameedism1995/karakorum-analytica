from app.processors.confidence_scorer import incident_status_from_score, score_confidence


def test_one_source_score():
    assert score_confidence(["GDELT"]) == 33.33


def test_two_source_score():
    assert score_confidence(["GDELT", "ReliefWeb"]) == 66.66


def test_three_source_score():
    assert score_confidence(["GDELT", "ReliefWeb", "ACLED"]) == 100.0


def test_status_boundaries():
    assert incident_status_from_score(33.33) == "save_only"
    assert incident_status_from_score(33.34) == "needs_review"
    assert incident_status_from_score(66.66) == "needs_review"
    assert incident_status_from_score(66.67) == "ready_for_review"
    assert incident_status_from_score(100.0) == "ready_for_review"
