-- Rename zapier_response to buffer_response for direct Buffer API
ALTER TABLE public.posts ADD COLUMN IF NOT EXISTS buffer_response JSONB;

UPDATE public.posts
SET buffer_response = zapier_response::jsonb
WHERE buffer_response IS NULL AND zapier_response IS NOT NULL;

ALTER TABLE public.posts DROP COLUMN IF EXISTS zapier_response;

COMMENT ON TABLE public.posts IS 'Human-approved editorial posts for Buffer/X via Buffer API';
