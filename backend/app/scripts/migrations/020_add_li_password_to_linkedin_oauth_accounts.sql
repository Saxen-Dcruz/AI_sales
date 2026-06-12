-- Adds li_password column to linkedin_oauth_accounts.
-- Stores the account password used by the headless session-refresh flow when
-- the LinkedIn OAuth access token expires (LinkedIn does not expose a refresh
-- token for member tokens). Nullable: existing rows / accounts that don't use
-- the auto-refresh path stay NULL.
--
-- Rollback: ALTER TABLE linkedin_oauth_accounts DROP COLUMN IF EXISTS li_password;

ALTER TABLE linkedin_oauth_accounts
    ADD COLUMN IF NOT EXISTS li_password TEXT;
