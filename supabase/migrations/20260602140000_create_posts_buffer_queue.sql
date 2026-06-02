-- Editorial posts queue for Buffer/X publishing via Zapier
CREATE TABLE IF NOT EXISTS public.posts (
    id SERIAL PRIMARY KEY,
    draft_post_id INTEGER UNIQUE REFERENCES public.draft_posts (id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'drafted',
    post_text TEXT NOT NULL DEFAULT '',
    headline TEXT,
    source_url TEXT,
    source_name TEXT,
    verification_status TEXT,
    source_grade TEXT,
    image_url TEXT,
    scheduled_time TIMESTAMPTZ,
    graphic_content BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    zapier_response JSONB,
    sent_to_buffer_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_posts_status ON public.posts (status);
CREATE INDEX IF NOT EXISTS idx_posts_draft_post_id ON public.posts (draft_post_id);
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON public.posts (created_at DESC);

COMMENT ON TABLE public.posts IS 'Human-approved editorial posts for Buffer/X via Zapier';

-- Backfill from existing draft_posts without breaking data
INSERT INTO public.posts (
    draft_post_id,
    status,
    post_text,
    headline,
    source_name,
    source_grade,
    verification_status,
    graphic_content,
    created_at
)
SELECT
    d.id,
    CASE d.status
        WHEN 'pending' THEN 'needs_review'
        WHEN 'approved' THEN 'approved'
        WHEN 'posted' THEN 'sent_to_buffer'
        WHEN 'rejected' THEN 'failed'
        ELSE 'drafted'
    END,
    COALESCE(d.post_text, ''),
    i.main_title,
    i.matched_sources,
    CASE
        WHEN d.confidence_score >= 80 THEN 'A'
        WHEN d.confidence_score >= 66 THEN 'B'
        WHEN d.confidence_score >= 33 THEN 'C'
        WHEN d.confidence_score >= 15 THEN 'D'
        ELSE 'E'
    END,
    'unverified',
    FALSE,
    d.created_at
FROM public.draft_posts d
LEFT JOIN public.incidents i ON i.id = d.incident_id
WHERE NOT EXISTS (
    SELECT 1 FROM public.posts p WHERE p.draft_post_id = d.id
);
