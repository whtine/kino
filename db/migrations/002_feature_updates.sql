-- Apply after 001_init.sql. Safe to run on databases created from the older schema.
CREATE TABLE IF NOT EXISTS chat_reputation (
    chat_id BIGINT REFERENCES chats(chat_id) ON DELETE CASCADE,
    voter_id BIGINT NOT NULL,
    target_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, voter_id, target_id),
    CHECK (voter_id <> target_id)
);

CREATE TABLE IF NOT EXISTS chat_bans (
    chat_id BIGINT REFERENCES chats(chat_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    reason TEXT,
    banned_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_reputation_target
    ON chat_reputation(chat_id, target_id);
CREATE INDEX IF NOT EXISTS idx_chat_bans_user ON chat_bans(user_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chat_members_role_range'
    ) THEN
        ALTER TABLE chat_members
            ADD CONSTRAINT chat_members_role_range CHECK (role BETWEEN 0 AND 6);
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION increment_message_stat(p_chat_id BIGINT, p_user_id BIGINT)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    updated_count BIGINT;
BEGIN
    INSERT INTO message_stats (chat_id, user_id, count, last_message_at)
    VALUES (p_chat_id, p_user_id, 1, NOW())
    ON CONFLICT (chat_id, user_id) DO UPDATE
    SET count = message_stats.count + 1,
        last_message_at = NOW()
    RETURNING count INTO updated_count;

    RETURN updated_count;
END;
$$;
