-- Migration 017: Multi-account Gmail support
-- Creates email_accounts table to store OAuth tokens for multiple Gmail accounts
-- Rollback: DROP TABLE IF EXISTS email_accounts;

CREATE TABLE IF NOT EXISTS email_accounts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_address VARCHAR UNIQUE NOT NULL,
    display_name  VARCHAR,
    token_data    TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    is_primary    BOOLEAN NOT NULL DEFAULT FALSE,
    scopes        JSONB,
    added_by      VARCHAR,
    created_at    VARCHAR NOT NULL DEFAULT now()::TEXT,
    updated_at    VARCHAR NOT NULL DEFAULT now()::TEXT
);

CREATE INDEX IF NOT EXISTS idx_email_accounts_active ON email_accounts (is_active);

-- Add account_id to emails table so each email tracks which Gmail account processed it
ALTER TABLE emails ADD COLUMN IF NOT EXISTS account_id   UUID REFERENCES email_accounts(id) ON DELETE SET NULL;
ALTER TABLE emails ADD COLUMN IF NOT EXISTS account_email VARCHAR;

CREATE INDEX IF NOT EXISTS idx_emails_account_id ON emails (account_id);
