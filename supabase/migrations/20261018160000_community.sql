-- Community reviews. The service role bypasses RLS. The API still checks the author
-- and the owner, because these policies cannot see a Telegram id.
-- Anon and authenticated clients can read approved reviews only.
-- The moderation queue has RLS and no policy for those roles.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    nick TEXT,
    country TEXT NOT NULL,
    city TEXT NOT NULL,
    trip_date_start DATE NOT NULL,
    trip_date_end DATE NOT NULL,
    topic TEXT NOT NULL CHECK (topic IN ('payment', 'bank_card', 'tax_free', 'transfer', 'border_visa', 'connectivity')),
    action_text TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('success', 'fail', 'partial')),
    changed_text TEXT,
    amount NUMERIC,
    currency TEXT,
    fee NUMERIC,
    fee_kind TEXT CHECK (fee_kind IS NULL OR fee_kind IN ('amount', 'percent')),
    duration_min NUMERIC,
    place_type TEXT CHECK (place_type IS NULL OR place_type IN ('branch', 'airport', 'terminal', 'shop')),
    place_name TEXT,
    citizenship TEXT NOT NULL,
    payment_method TEXT CHECK (payment_method IS NULL OR payment_method IN ('mir', 'unionpay', 'foreign', 'cash', 'wallet')),
    photo_path TEXT,
    photo_redaction_status TEXT CHECK (photo_redaction_status IS NULL OR photo_redaction_status IN ('clean', 'needs_review')),
    ready_to_recheck BOOLEAN NOT NULL DEFAULT false,
    is_anonymous BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'idea')),
    antifraud_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    moderated_at TIMESTAMPTZ,
    recheck_reminded_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_reviews_user ON public.reviews (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON public.reviews (status);

CREATE TABLE IF NOT EXISTS public.review_fact_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    review_id UUID NOT NULL REFERENCES public.reviews (id) ON DELETE CASCADE,
    fact_id TEXT NOT NULL,
    user_id BIGINT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('confirms', 'refutes', 'partial')),
    verdict_source TEXT NOT NULL CHECK (verdict_source IN ('auto', 'owner')),
    counted BOOLEAN NOT NULL DEFAULT false,
    weight NUMERIC,
    not_counted_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_fact_links_fact ON public.review_fact_links (fact_id, counted);
CREATE INDEX IF NOT EXISTS idx_review_fact_links_user_fact ON public.review_fact_links (user_id, fact_id);

CREATE TABLE IF NOT EXISTS public.achievements (
    user_id BIGINT NOT NULL,
    code TEXT NOT NULL,
    scope TEXT NOT NULL,
    awarded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    review_id UUID,
    PRIMARY KEY (user_id, code, scope)
);

CREATE TABLE IF NOT EXISTS public.user_levels (
    user_id BIGINT PRIMARY KEY,
    counted_reviews INTEGER NOT NULL DEFAULT 0,
    accuracy NUMERIC,
    author_weight NUMERIC,
    helped_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fact_views (
    fact_id TEXT NOT NULL,
    user_id BIGINT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (fact_id, user_id)
);

CREATE TABLE IF NOT EXISTS public.moderation_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kind TEXT NOT NULL CHECK (kind IN ('review', 'dispute', 'idea')),
    trigger TEXT,
    target_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    decision TEXT,
    decided_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_moderation_queue_open ON public.moderation_queue (status, target_id);

ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.review_fact_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.achievements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_levels ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fact_views ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.moderation_queue ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS reviews_select_approved ON public.reviews;
CREATE POLICY reviews_select_approved ON public.reviews
    FOR SELECT TO anon, authenticated
    USING (status = 'approved');

DROP POLICY IF EXISTS review_fact_links_select_approved ON public.review_fact_links;
CREATE POLICY review_fact_links_select_approved ON public.review_fact_links
    FOR SELECT TO anon, authenticated
    USING (
        counted = true
        AND EXISTS (
            SELECT 1 FROM public.reviews
            WHERE reviews.id = review_fact_links.review_id
              AND reviews.status = 'approved'
        )
    );

GRANT SELECT ON public.reviews TO anon, authenticated;
GRANT SELECT ON public.review_fact_links TO anon, authenticated;
GRANT ALL ON public.reviews TO service_role;
GRANT ALL ON public.review_fact_links TO service_role;
GRANT ALL ON public.achievements TO service_role;
GRANT ALL ON public.user_levels TO service_role;
GRANT ALL ON public.fact_views TO service_role;
GRANT ALL ON public.moderation_queue TO service_role;

-- Private bucket for redacted review photos.
-- Supabase documents this insert as the SQL way to create a bucket:
-- https://supabase.com/docs/guides/storage/buckets/creating-buckets
-- public = false means there is no public URL.
-- storage.objects already has row level security. This migration adds no
-- permissive policy, so anon and authenticated cannot read or write objects.
-- The restrictive policy below still denies this bucket if some other policy
-- allows every bucket. service_role bypasses row level security; the Mini App
-- uploads with that key only.
-- File size stays at the project global limit. The app rejects larger files
-- using community.photo.max_bytes before the upload.

INSERT INTO storage.buckets (id, name, public, allowed_mime_types)
VALUES ('community-photos', 'community-photos', false, ARRAY['image/jpeg']::text[])
ON CONFLICT (id) DO UPDATE
SET
    name = EXCLUDED.name,
    public = false,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

DROP POLICY IF EXISTS community_photos_block_clients ON storage.objects;
CREATE POLICY community_photos_block_clients
ON storage.objects
AS RESTRICTIVE
FOR ALL
TO anon, authenticated
USING (bucket_id IS DISTINCT FROM 'community-photos')
WITH CHECK (bucket_id IS DISTINCT FROM 'community-photos');
