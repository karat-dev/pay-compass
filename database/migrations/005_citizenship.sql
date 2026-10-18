-- Mirror of supabase/migrations/20261017120000_citizenship.sql
ALTER TABLE public.miniapp_profiles
    ADD COLUMN IF NOT EXISTS citizenship TEXT NOT NULL DEFAULT 'ru';
