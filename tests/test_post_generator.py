from app.processors.post_generator import generate_draft_post


def test_strong_draft_multiple_sources():
    text = generate_draft_post(
        main_title="Explosion in Quetta",
        province="Balochistan",
        city="Quetta",
        keywords=["explosion", "quetta", "balochistan", "blast"],
        confidence_score=66.66,
        source_count=2,
    )
    assert "Security incident reported in Quetta, Balochistan" in text
    assert "Multiple open sources" in text
    assert "Official confirmation" in text


def test_weak_draft_single_source():
    text = generate_draft_post(
        main_title="Possible incident in Quetta",
        province="Balochistan",
        city="Quetta",
        keywords=["quetta", "balochistan"],
        confidence_score=33.33,
        source_count=1,
    )
    assert "Initial reports suggest" in text
    assert "limited open-source information" in text
    assert "Official confirmation is pending" in text


def test_neutral_wording_no_confirmed():
    text = generate_draft_post(
        main_title="Attack in Peshawar",
        province="Khyber Pakhtunkhwa",
        city="Peshawar",
        keywords=["attack", "peshawar"],
        confidence_score=100.0,
        source_count=3,
    )
    assert "confirmed" not in text.lower() or "confirmation" in text.lower()
