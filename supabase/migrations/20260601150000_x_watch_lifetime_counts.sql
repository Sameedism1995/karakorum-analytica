ALTER TABLE public.x_watch_accounts
    ADD COLUMN IF NOT EXISTS total_tweets_fetched INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_tweets_saved INTEGER NOT NULL DEFAULT 0;
