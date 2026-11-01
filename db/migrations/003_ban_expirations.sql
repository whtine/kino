-- Apply after 002_feature_updates.sql. Existing bans remain permanent.
ALTER TABLE global_bans
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

ALTER TABLE chat_bans
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
