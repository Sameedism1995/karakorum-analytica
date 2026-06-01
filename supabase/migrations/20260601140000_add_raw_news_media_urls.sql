ALTER TABLE public.raw_news
    ADD COLUMN IF NOT EXISTS media_urls TEXT;

COMMENT ON COLUMN public.raw_news.media_urls IS 'JSON array of Supabase Storage public URLs for attached images/videos';
