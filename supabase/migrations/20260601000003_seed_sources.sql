-- Karakorum Analytica — seed default sources on remote Supabase (idempotent)
-- Duplicate of supabase/seed.sql for `supabase db push` without db reset.

INSERT INTO public.sources (name, api_url, weight, is_active) VALUES
    ('GDELT', 'https://api.gdeltproject.org/api/v2/doc/doc', 33.33, TRUE),
    ('ReliefWeb', 'https://api.reliefweb.int/v2/reports', 33.33, TRUE),
    ('ACLED', 'https://acleddata.com/api/acled/read', 33.33, TRUE),
    ('X/Scweet', 'https://github.com/Altimis/Scweet', 33.33, TRUE)
ON CONFLICT (name) DO UPDATE SET
    api_url = EXCLUDED.api_url,
    weight = EXCLUDED.weight,
    is_active = EXCLUDED.is_active;
