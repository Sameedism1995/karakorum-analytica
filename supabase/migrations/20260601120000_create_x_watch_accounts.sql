-- Watched X profiles (timeline polling)

CREATE TABLE IF NOT EXISTS public.x_watch_accounts (
    id SERIAL PRIMARY KEY,
    handle VARCHAR(64) NOT NULL UNIQUE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_fetched_at TIMESTAMPTZ,
    last_tweet_count INTEGER NOT NULL DEFAULT 0,
    last_saved_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_x_watch_accounts_enabled ON public.x_watch_accounts (enabled);
CREATE INDEX IF NOT EXISTS idx_x_watch_accounts_last_fetched ON public.x_watch_accounts (last_fetched_at DESC NULLS LAST);

COMMENT ON TABLE public.x_watch_accounts IS 'X handles polled for profile timelines; tweets saved to raw_news';
