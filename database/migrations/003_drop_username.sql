-- Launch stores a Telegram id plus settings, progress and reports.
-- Names, usernames and phone numbers are not stored.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'users'
    ) THEN
        ALTER TABLE users DROP COLUMN IF EXISTS username;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'miniapp_profiles'
    ) THEN
        ALTER TABLE miniapp_profiles DROP COLUMN IF EXISTS username;
    END IF;
END $$;
