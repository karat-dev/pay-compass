-- Mirror of supabase/migrations/20261017000000_intro_seen.sql
ALTER TABLE public.miniapp_profiles
    ADD COLUMN IF NOT EXISTS intro_seen BOOLEAN NOT NULL DEFAULT false;
