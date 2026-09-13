-- Migration 001: Initial Schema for Independent Payment Guide
-- Contains 16 tables covering countries, verified facts, sources, user access & FSM states,
-- stars subscriptions, legal consent, and partners.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. COUNTRIES
CREATE TABLE IF NOT EXISTS countries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 2. SOURCES (Hierarchical trust_score: Official=10, Media=7, Telegram=3)
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('official', 'media', 'telegram')),
    trust_score INT NOT NULL,
    last_parsed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'degraded', 'down', 'pending'))
);

-- 3. SOURCE HEALTH (Tracking failures, degraded states, and alerts)
CREATE TABLE IF NOT EXISTS source_health (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'healthy' CHECK (status IN ('healthy', 'degraded', 'down')),
    error_count INT DEFAULT 0,
    last_failure_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ
);

-- 4. RAW POSTS (Incoming unverified content from Crawlee / Telethon / RSS)
CREATE TABLE IF NOT EXISTS raw_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    parsed_at TIMESTAMPTZ DEFAULT now(),
    processed BOOLEAN DEFAULT false
);

-- 5. VERIFIED FACTS (FactVerifAI processed facts with required source, date, confidence)
CREATE TABLE IF NOT EXISTS verified_facts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id UUID NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    fact TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    sources JSONB NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL,
    cross_check_count INT DEFAULT 0
);

-- 6. PAYMENT METHODS (Specific cards/payment channels per country)
CREATE TABLE IF NOT EXISTS payment_methods (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id UUID NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    works BOOLEAN NOT NULL,
    commission TEXT,
    limits TEXT,
    source_url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL,
    confidence FLOAT NOT NULL
);

-- 7. WARNINGS (Scam and fraud alerts)
CREATE TABLE IF NOT EXISTS warnings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id UUID NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    scam_type TEXT NOT NULL,
    description TEXT NOT NULL,
    source_url TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    confidence FLOAT NOT NULL
);

-- 8. USERS (Privacy-first: only telegram_id, consent tracking according to 152-FZ)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    consent_given BOOLEAN DEFAULT false,
    consent_date TIMESTAMPTZ,
    onboarding_step INT DEFAULT 1,
    last_seen_at TIMESTAMPTZ DEFAULT now(),
    subscription_status TEXT DEFAULT 'free' CHECK (subscription_status IN ('free', 'premium')),
    subscription_expires_at TIMESTAMPTZ
);

-- 9. USER STATES (Persistent FSM storage for aiogram 3.x)
CREATE TABLE IF NOT EXISTS user_states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT UNIQUE NOT NULL,
    state TEXT,
    data JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 10. EVENTS (Product analytics & funnel drop-off tracking)
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    event_type TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 11. USER COUNTRY ACCESS (Enforces "1 country per week free" limit)
CREATE TABLE IF NOT EXISTS user_country_access (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    country_id UUID NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    unlocked_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- 12. USER REPORTS ("Report an error" button feedback)
CREATE TABLE IF NOT EXISTS user_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fact_id UUID REFERENCES verified_facts(id) ON DELETE SET NULL,
    user_id BIGINT NOT NULL,
    report_type TEXT NOT NULL,
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 13. SUBSCRIPTIONS (Telegram Stars payments: 90 days access)
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'refunded')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    stars_paid INT NOT NULL,
    transaction_id TEXT UNIQUE NOT NULL
);

-- 14. PARTNERS (Curated partners with strictly monitored trust_score)
CREATE TABLE IF NOT EXISTS partners (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    service_type TEXT NOT NULL,
    trust_score FLOAT NOT NULL CHECK (trust_score >= 0 AND trust_score <= 100),
    referral_url TEXT NOT NULL,
    description TEXT,
    verified_at TIMESTAMPTZ NOT NULL,
    is_affiliate BOOLEAN DEFAULT true,
    is_active BOOLEAN DEFAULT false
);

-- 15. CARD INSTRUCTIONS (Country guide: How to open a card)
CREATE TABLE IF NOT EXISTS card_instructions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id UUID NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    steps JSONB NOT NULL,
    requirements TEXT,
    timeline TEXT,
    cost TEXT,
    source_url TEXT NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL
);

-- 16. RECOMMENDATIONS (Country-partner matching filtered by trust_score >= 60)
CREATE TABLE IF NOT EXISTS recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id UUID NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    partner_id UUID NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT false
);

-- INDEXES for fast lookup
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_user_states_user_id ON user_states(user_id);
CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_user_country_access_user ON user_country_access(user_id);
CREATE INDEX IF NOT EXISTS idx_verified_facts_country ON verified_facts(country_id);
CREATE INDEX IF NOT EXISTS idx_payment_methods_country ON payment_methods(country_id);
CREATE INDEX IF NOT EXISTS idx_warnings_country ON warnings(country_id);

-- ENABLE ROW LEVEL SECURITY (RLS) FOR ALL TABLES
ALTER TABLE countries ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE verified_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_methods ENABLE ROW LEVEL SECURITY;
ALTER TABLE warnings ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_country_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE partners ENABLE ROW LEVEL SECURITY;
ALTER TABLE card_instructions ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendations ENABLE ROW LEVEL SECURITY;

-- SERVICE ROLE ACCESS (Full access for backend bot/scrapers with service_role key)
-- Public read access for read-only tables (countries, verified facts, payment methods, warnings)
DROP POLICY IF EXISTS "Public read access for countries" ON countries;
CREATE POLICY "Public read access for countries" ON countries FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read access for verified_facts" ON verified_facts;
CREATE POLICY "Public read access for verified_facts" ON verified_facts FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read access for payment_methods" ON payment_methods;
CREATE POLICY "Public read access for payment_methods" ON payment_methods FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read access for warnings" ON warnings;
CREATE POLICY "Public read access for warnings" ON warnings FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read access for card_instructions" ON card_instructions;
CREATE POLICY "Public read access for card_instructions" ON card_instructions FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read access for recommendations" ON recommendations;
CREATE POLICY "Public read access for recommendations" ON recommendations FOR SELECT USING (true);
