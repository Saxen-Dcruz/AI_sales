-- Migration 003: refresh_tokens table
-- Stores hashed refresh tokens for session revocation and rotation.
-- Rollback: DROP TABLE IF EXISTS refresh_tokens;

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR     NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE        INDEX IF NOT EXISTS ix_refresh_tokens_user_id    ON refresh_tokens(user_id);
