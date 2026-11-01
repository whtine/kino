-- VK Bot Database Schema for Supabase (PostgreSQL)
-- Run this in Supabase SQL Editor

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Chat Groups (for global commands across multiple chats)
CREATE TABLE chat_groups (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id BIGINT NOT NULL,           -- VK user_id of group owner
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Chats (conversations where bot is added)
CREATE TABLE chats (
    chat_id BIGINT PRIMARY KEY,         -- VK peer_id (2000000000+)
    title TEXT,
    is_active BOOLEAN DEFAULT FALSE,    -- activated by * command
    settings JSONB DEFAULT '{}',        -- antitag, timeout, etc.
    group_id BIGINT REFERENCES chat_groups(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Chat Group Bindings (many-to-many: chats <-> groups)
CREATE TABLE chat_group_bindings (
    chat_id BIGINT REFERENCES chats(chat_id) ON DELETE CASCADE,
    group_id BIGINT REFERENCES chat_groups(id) ON DELETE CASCADE,
    PRIMARY KEY (chat_id, group_id)
);

-- 4. Chat Members (users in chats with roles)
CREATE TABLE chat_members (
    chat_id BIGINT REFERENCES chats(chat_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,            -- VK user_id
    role INT DEFAULT 0 CONSTRAINT chat_members_role_range CHECK (role BETWEEN 0 AND 6),
    nickname TEXT,                      -- local nickname in this chat
    warns INT DEFAULT 0,                -- active warnings count
    is_muted BOOLEAN DEFAULT FALSE,
    muted_until TIMESTAMPTZ,
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id)
);

-- 5. Global Bans (per chat group)
CREATE TABLE global_bans (
    group_id BIGINT REFERENCES chat_groups(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    reason TEXT,
    banned_by BIGINT,                   -- moderator who banned
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (group_id, user_id)
);

-- 6. Global Nicknames (per chat group)
CREATE TABLE global_nicknames (
    group_id BIGINT REFERENCES chat_groups(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    nickname TEXT NOT NULL,
    set_by BIGINT,                      -- moderator who set
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (group_id, user_id)
);

-- 7. Punishments History (logs)
CREATE TABLE punishments (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT REFERENCES chats(chat_id) ON DELETE CASCADE,
    target_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    type TEXT NOT NULL,                 -- kick, mute, warn, ban, unban, unwarn, unmute, gban, gunban
    reason TEXT,
    duration INTERVAL,                  -- for temporary mutes/bans
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Message Statistics (for /top command)
CREATE TABLE message_stats (
    chat_id BIGINT REFERENCES chats(chat_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    count BIGINT DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    PRIMARY KEY (chat_id, user_id)
);

-- A user can give one reputation point to each other user in a chat.
CREATE TABLE chat_reputation (
    chat_id BIGINT REFERENCES chats(chat_id) ON DELETE CASCADE,
    voter_id BIGINT NOT NULL,
    target_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, voter_id, target_id),
    CHECK (voter_id <> target_id)
);

-- Local bans are separate from group-wide bans.
CREATE TABLE chat_bans (
    chat_id BIGINT REFERENCES chats(chat_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    reason TEXT,
    banned_by BIGINT NOT NULL,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id)
);

-- Indexes for performance
CREATE INDEX idx_chat_members_role ON chat_members(chat_id, role);
CREATE INDEX idx_chat_members_user ON chat_members(user_id);
CREATE INDEX idx_punishments_chat_target ON punishments(chat_id, target_id);
CREATE INDEX idx_punishments_target ON punishments(target_id);
CREATE INDEX idx_punishments_created ON punishments(created_at DESC);
CREATE INDEX idx_message_stats_top ON message_stats(chat_id, count DESC);
CREATE INDEX idx_chat_reputation_target ON chat_reputation(chat_id, target_id);
CREATE INDEX idx_chat_bans_user ON chat_bans(user_id);
CREATE INDEX idx_global_bans_user ON global_bans(user_id);
CREATE INDEX idx_global_nicknames_user ON global_nicknames(user_id);
CREATE INDEX idx_chats_group ON chats(group_id);
CREATE INDEX idx_chats_active ON chats(is_active) WHERE is_active = TRUE;

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_chat_groups_updated_at BEFORE UPDATE ON chat_groups
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chats_updated_at BEFORE UPDATE ON chats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chat_members_updated_at BEFORE UPDATE ON chat_members
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Use an atomic upsert so concurrent messages cannot lose statistics.
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