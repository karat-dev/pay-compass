-- First-run intro flag. Existing rows stay unseen until the app marks them.
-- Does not rewrite trip dates: an auto-filled "today" cannot be told apart later.
ALTER TABLE public.miniapp_profiles
    ADD COLUMN IF NOT EXISTS intro_seen BOOLEAN NOT NULL DEFAULT false;
