"""Tests for LLM newsroom dashboard service."""

from app.schemas.llm_dashboard import (
    AuditPostRequest,
    GeneratePostRequest,
    KeywordPostRequest,
    SeoRequest,
)
from app.services.llm_newsroom_service import (
    audit_post,
    generate_post,
    keyword_post,
    seo_assist,
)


def test_generate_post_without_incident_text_is_template():
    result = generate_post(
        GeneratePostRequest(
            main_keyword="Balochistan security",
            region="Balochistan",
        )
    )
    assert result.mode == "template"
    assert result.verification_warning
    assert "unverified" in result.website_post.lower() or "verification" in result.website_post.lower()


def test_generate_post_with_incident_text():
    result = generate_post(
        GeneratePostRequest(
            raw_incident_text=(
                "Open sources report an IED incident near Quetta. "
                "Local media cite police officials. No official casualty count."
            ),
            main_keyword="Quetta IED",
            region="Balochistan",
            city_district="Quetta",
            source_type="local media",
            source_reliability_grade="C",
        )
    )
    assert result.mode in {"generated", "template", "ollama"}
    assert "Quetta" in result.short_x_post
    assert result.seo_headline


def test_keyword_post_without_verified_text_is_template_only():
    result = keyword_post(KeywordPostRequest(topic_keyword="KP attack", region="KP"))
    assert result.mode == "template"
    assert "NOT A NEWS REPORT" in result.full_news_update or "TEMPLATE" in result.full_news_update
    assert len(result.headline_options) == 5
    assert len(result.short_posts) == 3
    assert len(result.source_verification_checklist) >= 3


def test_audit_post_flags_sensational_language():
    result = audit_post(
        AuditPostRequest(
            draft_post="BREAKING: Shocking massacre confirmed dead in Quetta.",
            source_information="Grade D social media rumor",
            raw_report_text="Unverified social post.",
        )
    )
    assert result.risk_score >= 40
    assert result.sensational_wording
    assert result.publish_status in {
        "publish_with_caution",
        "needs_verification",
        "do_not_publish",
    }


def test_seo_assist_returns_slug_and_meta():
    result = seo_assist(
        SeoRequest(
            incident_summary="Monitoring reports in Balochistan border area.",
            main_keyword="Balochistan border",
            secondary_keywords="security, OSINT",
        )
    )
    assert result.url_slug
    assert result.meta_description
    assert "Balochistan" in result.article_tags[0] or any(
        "balochistan" in t.lower() for t in result.article_tags
    )
