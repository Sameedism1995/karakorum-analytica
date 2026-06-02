-- Editorial metadata for local LLM drafts and approval workflow
ALTER TABLE public.posts ADD COLUMN IF NOT EXISTS risk_flags JSONB;
ALTER TABLE public.posts ADD COLUMN IF NOT EXISTS editor_notes JSONB;
ALTER TABLE public.posts ADD COLUMN IF NOT EXISTS publish_recommendation TEXT;
ALTER TABLE public.posts ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;

COMMENT ON TABLE public.posts IS 'Human-approved editorial posts for Buffer/X via Buffer API';
