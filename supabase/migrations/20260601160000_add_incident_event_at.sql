ALTER TABLE public.incidents
    ADD COLUMN IF NOT EXISTS event_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_incidents_event_at ON public.incidents (event_at DESC NULLS LAST);

COMMENT ON COLUMN public.incidents.event_at IS 'Latest published_at from grouped raw news (reported event time)';
