-- Karakorum Analytica — Supabase / PostgreSQL schema
-- Run in Supabase SQL Editor, or let `python scripts/init_db.py` create tables via SQLAlchemy.

CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE,
    api_url VARCHAR(512) NOT NULL,
    weight DOUBLE PRECISION NOT NULL DEFAULT 33.33,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw_news (
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

CREATE INDEX IF NOT EXISTS ix_raw_news_source_name ON raw_news (source_name);
CREATE INDEX IF NOT EXISTS ix_raw_news_url ON raw_news (url);
CREATE INDEX IF NOT EXISTS ix_raw_news_content_hash ON raw_news (content_hash);

CREATE TABLE IF NOT EXISTS incidents (
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

CREATE TABLE IF NOT EXISTS draft_posts (
    id SERIAL PRIMARY KEY,
    incident_id INTEGER NOT NULL REFERENCES incidents (id),
    post_text TEXT NOT NULL,
    keywords TEXT,
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    approved_at TIMESTAMPTZ,
    posted_at TIMESTAMPTZ,
    x_post_id VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_draft_posts_incident_id ON draft_posts (incident_id);

CREATE TABLE IF NOT EXISTS posted_items (
    id SERIAL PRIMARY KEY,
    draft_post_id INTEGER NOT NULL REFERENCES draft_posts (id),
    platform VARCHAR(32) NOT NULL DEFAULT 'x',
    platform_post_id VARCHAR(128),
    post_url VARCHAR(2048),
    posted_at TIMESTAMPTZ NOT NULL,
    response_json TEXT
);

CREATE INDEX IF NOT EXISTS ix_posted_items_draft_post_id ON posted_items (draft_post_id);

-- Default API sources (same as app/bootstrap.py)
INSERT INTO sources (name, api_url, weight, is_active) VALUES
    ('GDELT', 'https://api.gdeltproject.org/api/v2/doc/doc', 33.33, TRUE),
    ('ReliefWeb', 'https://api.reliefweb.int/v2/reports', 33.33, TRUE),
    ('ACLED', 'https://acleddata.com/api/acled/read', 33.33, TRUE)
ON CONFLICT (name) DO NOTHING;

-- Optional: enable Row Level Security (backend uses service role / direct Postgres)
-- ALTER TABLE raw_news ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE draft_posts ENABLE ROW LEVEL SECURITY;
