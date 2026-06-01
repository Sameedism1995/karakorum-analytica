from typing import Literal

from pydantic import BaseModel, Field


ToneOption = Literal["neutral", "urgent", "detailed", "short"]
PlatformOption = Literal["x", "website", "telegram", "instagram"]
PublishStatusOption = Literal[
    "safe_to_publish",
    "publish_with_caution",
    "needs_verification",
    "do_not_publish",
]
SavedStatusOption = Literal["draft", "reviewed", "ready", "rejected"]


class GeneratePostRequest(BaseModel):
    raw_incident_text: str = ""
    main_keyword: str = ""
    seo_keywords: str = ""
    region: str = ""
    country: str = "Pakistan"
    city_district: str = ""
    incident_category: str = ""
    source_type: str = ""
    source_reliability_grade: str = "C"
    tone: ToneOption = "neutral"
    platform: PlatformOption = "x"


class KeywordPostRequest(BaseModel):
    topic_keyword: str
    seo_keywords: str = ""
    target_audience: str = ""
    region: str = ""
    time_sensitivity: str = "standard"
    verified_incident_text: str = ""


class AuditPostRequest(BaseModel):
    draft_post: str
    source_information: str = ""
    raw_report_text: str = ""


class SeoRequest(BaseModel):
    incident_summary: str = ""
    article_draft: str = ""
    main_keyword: str = ""
    secondary_keywords: str = ""


class SavePostRequest(BaseModel):
    content_type: str
    raw_input: dict | str
    generated_output: dict | str
    source_grade: str | None = None
    keywords: str | None = None
    seo_keywords: str | None = None
    region: str | None = None
    category: str | None = None
    audit_score: float | None = None
    status: SavedStatusOption = "draft"


class UpdateStatusRequest(BaseModel):
    status: SavedStatusOption


class GeneratePostResponse(BaseModel):
    short_x_post: str
    website_post: str
    seo_headline: str
    meta_description: str
    suggested_hashtags: list[str]
    suggested_keywords: list[str]
    verification_warning: str | None = None
    mode: str = "generated"
    editorial_notes: list[str] = Field(default_factory=list)


class KeywordPostResponse(BaseModel):
    headline_options: list[str]
    short_posts: list[str]
    full_news_update: str
    hashtags: list[str]
    recommended_caution_line: str
    source_verification_checklist: list[str]
    mode: str = "template"
    editorial_notes: list[str] = Field(default_factory=list)


class AuditPostResponse(BaseModel):
    risk_score: int
    source_reliability_grade: str
    unsupported_claims: list[str]
    sensational_wording: list[str]
    propaganda_wording: list[str]
    legal_safety_risk: list[str]
    safer_rewritten_version: str
    publish_status: PublishStatusOption
    publish_status_label: str
    editorial_notes: list[str] = Field(default_factory=list)


class SeoResponse(BaseModel):
    seo_title: str
    url_slug: str
    meta_description: str
    article_tags: list[str]
    internal_categories: list[str]
    search_friendly_summary: str
    social_media_caption: str
    editorial_notes: list[str] = Field(default_factory=list)


class SavedPostItem(BaseModel):
    id: int
    content_type: str
    raw_input: dict | str
    generated_output: dict | str
    source_grade: str | None = None
    keywords: str | None = None
    seo_keywords: str | None = None
    region: str | None = None
    category: str | None = None
    audit_score: float | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None
