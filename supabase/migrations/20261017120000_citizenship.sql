-- Passport setting so later copy can branch by citizenship.
-- Only "ru" is offered. Existing rows stay Russian citizens. No other personal data.
ALTER TABLE public.miniapp_profiles
    ADD COLUMN IF NOT EXISTS citizenship TEXT NOT NULL DEFAULT 'ru';
