-- Karakorum Analytica — API roles and optional RLS
-- Backend uses direct Postgres (service role) which bypasses RLS.

GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role;

GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO postgres, service_role, authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO postgres, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO postgres, service_role, authenticated;

-- RLS disabled by default — enable per-table if exposing Supabase REST to browsers.
-- Example (uncomment when needed):
-- ALTER TABLE public.raw_news ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "service_role_all" ON public.raw_news FOR ALL TO service_role USING (true) WITH CHECK (true);
