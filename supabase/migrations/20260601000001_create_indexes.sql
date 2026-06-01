-- Karakorum Analytica — indexes for lookups and dashboard stats

-- raw_news
CREATE INDEX IF NOT EXISTS ix_raw_news_source_name ON public.raw_news (source_name);
CREATE INDEX IF NOT EXISTS ix_raw_news_url ON public.raw_news (url);
CREATE INDEX IF NOT EXISTS ix_raw_news_content_hash ON public.raw_news (content_hash);
CREATE INDEX IF NOT EXISTS ix_raw_news_collected_at ON public.raw_news (collected_at DESC);
CREATE INDEX IF NOT EXISTS ix_raw_news_status ON public.raw_news (status);

-- incidents
CREATE INDEX IF NOT EXISTS ix_incidents_status ON public.incidents (status);
CREATE INDEX IF NOT EXISTS ix_incidents_created_at ON public.incidents (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_incidents_country ON public.incidents (country);

-- draft_posts
CREATE INDEX IF NOT EXISTS ix_draft_posts_incident_id ON public.draft_posts (incident_id);
CREATE INDEX IF NOT EXISTS ix_draft_posts_status ON public.draft_posts (status);
CREATE INDEX IF NOT EXISTS ix_draft_posts_created_at ON public.draft_posts (created_at DESC);

-- posted_items
CREATE INDEX IF NOT EXISTS ix_posted_items_draft_post_id ON public.posted_items (draft_post_id);
CREATE INDEX IF NOT EXISTS ix_posted_items_posted_at ON public.posted_items (posted_at DESC);

-- sources
CREATE INDEX IF NOT EXISTS ix_sources_is_active ON public.sources (is_active);
