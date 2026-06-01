-- LLM newsroom saved outputs (Postgres / Supabase)
CREATE TABLE IF NOT EXISTS llm_saved_posts (
    id SERIAL PRIMARY KEY,
    content_type VARCHAR(64) NOT NULL,
    raw_input TEXT NOT NULL,
    generated_output TEXT NOT NULL,
    source_grade VARCHAR(8),
    keywords TEXT,
    seo_keywords TEXT,
    region VARCHAR(128),
    category VARCHAR(128),
    audit_score DOUBLE PRECISION,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_llm_saved_posts_status ON llm_saved_posts(status);
CREATE INDEX IF NOT EXISTS idx_llm_saved_posts_content_type ON llm_saved_posts(content_type);
