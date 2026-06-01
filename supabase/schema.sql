-- Karakorum Analytica — full PostgreSQL schema (Supabase)
-- For manual runs in Supabase SQL Editor. Prefer CLI migrations in supabase/migrations/.

-- ── Tables ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE,
    api_url VARCHAR(512) NOT NULL,
    weight DOUBLE PRECISION NOT NULL DEFAULT 33.33,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.raw_news (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(64) NOT NULL,
    title VARCHAR(1024),
    summary TEXT,
    url VARCHAR(2048),
    published_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL,
    country VARCHAR(64),
    province VARCHAR(128),
    city VARCHAR(128),
    raw_json TEXT,
    content_hash VARCHAR(64) NOT NULL UNIQUE,
    status VARCHAR(32) NOT NULL DEFAULT 'collected'
);

CREATE TABLE IF NOT EXISTS public.incidents (
    id SERIAL PRIMARY KEY,
    main_title VARCHAR(1024) NOT NULL,
    country VARCHAR(64) NOT NULL DEFAULT 'Pakistan',
    province VARCHAR(128),
    city VARCHAR(128),
    event_type VARCHAR(128),
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    matched_sources VARCHAR(256),
    keywords TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'save_only',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.draft_posts (
    id SERIAL PRIMARY KEY,
    incident_id INTEGER NOT NULL REFERENCES public.incidents (id),
    post_text TEXT NOT NULL,
    keywords TEXT,
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    approved_at TIMESTAMPTZ,
    posted_at TIMESTAMPTZ,
    x_post_id VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.posted_items (
    id SERIAL PRIMARY KEY,
    draft_post_id INTEGER NOT NULL REFERENCES public.draft_posts (id),
    platform VARCHAR(32) NOT NULL DEFAULT 'x',
    platform_post_id VARCHAR(128),
    post_url VARCHAR(2048),
    posted_at TIMESTAMPTZ NOT NULL,
    response_json TEXT
);

-- ── Indexes ──────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS ix_raw_news_source_name ON public.raw_news (source_name);
CREATE INDEX IF NOT EXISTS ix_raw_news_url ON public.raw_news (url);
CREATE INDEX IF NOT EXISTS ix_raw_news_content_hash ON public.raw_news (content_hash);
CREATE INDEX IF NOT EXISTS ix_raw_news_collected_at ON public.raw_news (collected_at DESC);
CREATE INDEX IF NOT EXISTS ix_raw_news_status ON public.raw_news (status);

CREATE INDEX IF NOT EXISTS ix_incidents_status ON public.incidents (status);
CREATE INDEX IF NOT EXISTS ix_incidents_created_at ON public.incidents (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_incidents_country ON public.incidents (country);

CREATE INDEX IF NOT EXISTS ix_draft_posts_incident_id ON public.draft_posts (incident_id);
CREATE INDEX IF NOT EXISTS ix_draft_posts_status ON public.draft_posts (status);
CREATE INDEX IF NOT EXISTS ix_draft_posts_created_at ON public.draft_posts (created_at DESC);

CREATE INDEX IF NOT EXISTS ix_posted_items_draft_post_id ON public.posted_items (draft_post_id);
CREATE INDEX IF NOT EXISTS ix_posted_items_posted_at ON public.posted_items (posted_at DESC);

CREATE INDEX IF NOT EXISTS ix_sources_is_active ON public.sources (is_active);

-- ── Seed sources ─────────────────────────────────────────────────────────────

INSERT INTO public.sources (name, api_url, weight, is_active) VALUES
    ('GDELT', 'https://api.gdeltproject.org/api/v2/doc/doc', 33.33, TRUE),
    ('ReliefWeb', 'https://api.reliefweb.int/v2/reports', 33.33, TRUE),
    ('ACLED', 'https://acleddata.com/api/acled/read', 33.33, TRUE),
    ('X/Scweet', 'https://github.com/Altimis/Scweet', 33.33, TRUE)
ON CONFLICT (name) DO UPDATE SET
    api_url = EXCLUDED.api_url,
    weight = EXCLUDED.weight,
    is_active = EXCLUDED.is_active;
