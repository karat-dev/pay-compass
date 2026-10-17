-- Same migration as supabase/migrations/20261014000000_miniapp.sql.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Prefer the supabase/migrations copy: GitHub Actions applies that folder.

CREATE TABLE IF NOT EXISTS miniapp_profiles (
    telegram_id BIGINT PRIMARY KEY,
    bank_id TEXT,
    departure_city_id TEXT,
    favorite_countries JSONB NOT NULL DEFAULT '[]'::jsonb,
    notify_checklist BOOLEAN NOT NULL DEFAULT true,
    notify_trip BOOLEAN NOT NULL DEFAULT true,
    notify_alerts BOOLEAN NOT NULL DEFAULT false,
    consent_given BOOLEAN NOT NULL DEFAULT false,
    onboarding_completed BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS miniapp_trips (
    telegram_id BIGINT PRIMARY KEY,
    destination_slug TEXT NOT NULL,
    departure_city_id TEXT,
    depart_date DATE,
    return_date DATE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS miniapp_progress (
    telegram_id BIGINT NOT NULL,
    item_id TEXT NOT NULL,
    instruction_id TEXT,
    kind TEXT NOT NULL DEFAULT 'step' CHECK (kind IN ('step', 'checklist')),
    completed BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (telegram_id, item_id)
);

CREATE TABLE IF NOT EXISTS miniapp_fact_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT NOT NULL,
    fact_id TEXT NOT NULL,
    country_slug TEXT,
    section_key TEXT,
    instruction_id TEXT,
    fact_text TEXT NOT NULL,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_miniapp_fact_reports_user ON miniapp_fact_reports (telegram_id, created_at DESC);

ALTER TABLE miniapp_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE miniapp_trips ENABLE ROW LEVEL SECURITY;
ALTER TABLE miniapp_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE miniapp_fact_reports ENABLE ROW LEVEL SECURITY;
