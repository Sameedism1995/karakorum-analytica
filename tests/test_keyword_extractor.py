from app.processors.keyword_extractor import extract_keywords


def test_extract_keywords_from_title():
    keywords = extract_keywords(
        "Explosion reported in Quetta, Balochistan",
        "Police and security forces responded to the blast near a checkpoint.",
    )
    assert "explosion" in keywords
    assert "quetta" in keywords
    assert "balochistan" in keywords
    assert "blast" in keywords


def test_no_duplicate_keywords():
    keywords = extract_keywords("Blast blast explosion", "blast in Karachi")
    assert keywords.count("blast") == 1
