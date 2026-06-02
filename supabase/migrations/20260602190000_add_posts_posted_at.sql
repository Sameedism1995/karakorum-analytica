-- Track immediate publish timestamp for approve-and-post-now flow
ALTER TABLE public.posts ADD COLUMN IF NOT EXISTS posted_at TIMESTAMPTZ;
