-- Apply after 003_ban_expirations.sql. Roles 5 and 6 are retired.
UPDATE chat_members
SET role = 4
WHERE role > 4;

ALTER TABLE chat_members
    DROP CONSTRAINT IF EXISTS chat_members_role_range;

ALTER TABLE chat_members
    ADD CONSTRAINT chat_members_role_range CHECK (role BETWEEN 0 AND 4);
