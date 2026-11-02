-- Apply after 004_role_cap_4.sql.
CREATE TABLE command_aliases (
    user_id BIGINT NOT NULL,
    alias TEXT NOT NULL,
    command TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, alias),
    CHECK (alias ~ '^[a-z][a-z0-9_]{0,19}$'),
    CHECK (command ~ '^[a-z][a-z0-9_]{0,19}$')
);

CREATE INDEX idx_command_aliases_user_id ON command_aliases(user_id);
