"""Tests for stripping embedded attribution from draft post text."""

from app.services.draft_text_clean import sanitize_draft_post_text


def test_sanitize_removes_attribution_footer():
    raw = (
        "Open-source reports indicate activity near Quetta. "
        "Based on X/Scweet (reliability grade C). Further verification recommended. #Pakistan"
    )
    cleaned = sanitize_draft_post_text(raw)
    assert "Based on" not in cleaned
    assert "reliability grade" not in cleaned
    assert "Further verification recommended" not in cleaned
    assert "Quetta" in cleaned


def test_generate_post_no_attribution_in_short_text(monkeypatch):
    from app.schemas.llm_dashboard import GeneratePostRequest
    from app.services.llm_newsroom_service import generate_post

    monkeypatch.setattr(
        "app.services.llm_newsroom_service.LLMClient.is_configured",
        property(lambda self: False),
    )

    result = generate_post(
        GeneratePostRequest(
            raw_incident_text="Local media report an incident near Quetta. Police cited.",
            main_keyword="Quetta",
            region="Balochistan",
            source_type="X/Scweet",
            source_reliability_grade="C",
        )
    )
    assert "Based on" not in result.short_x_post
    assert "reliability grade" not in result.short_x_post.lower()
