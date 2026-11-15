-- Data API grants for public tables created without an explicit GRANT.
-- Since 2026-10-30 Supabase does not grant anon, authenticated, or service_role
-- on new public tables. Existing production grants stay as they are; a clean
-- replay of these migrations would otherwise leave the Data API with
-- permission denied (42501) for the service role.
-- This file only grants privileges. It does not change policies, RLS, or rows.
--
-- anon and authenticated receive no privileges here.
-- The Mini App browser calls /api/* and does not send the anon key.
-- countries, verified_facts, payment_methods, warnings, card_instructions,
-- and recommendations already have permissive SELECT policies, but nothing
-- in the client reads them through PostgREST with the anon key. The catalog
-- is built on the server, and the bot uses the service role. Granting SELECT
-- to anon would expose those tables on the Data API without a caller that
-- needs it. User and scraper tables stay closed to anon for the same reason.
-- reviews and review_fact_links already grant SELECT to anon and authenticated
-- in 20261018160000_community.sql. This migration does not change those grants.
--
-- Current tables use uuid_generate_v4() or bigint primary keys, so they own
-- no sequences. The sequence grant is idempotent and covers any sequence that
-- already exists in public.

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    public.countries,
    public.sources,
    public.source_health,
    public.raw_posts,
    public.verified_facts,
    public.payment_methods,
    public.warnings,
    public.users,
    public.user_states,
    public.events,
    public.user_country_access,
    public.user_reports,
    public.subscriptions,
    public.partners,
    public.card_instructions,
    public.recommendations,
    public.miniapp_profiles,
    public.miniapp_trips,
    public.miniapp_progress,
    public.miniapp_fact_reports
TO service_role;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
