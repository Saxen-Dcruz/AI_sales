-- Add auto_send_enabled flag to email_accounts.
-- When False, all Sales emails for this account go to draft_ready instead of
-- auto-sending. Required by the EmailAccount model (app/models/email_account.py);
-- the column was added to the model without a corresponding migration, causing
-- "column email_accounts.auto_send_enabled does not exist" at runtime.
--
-- Rollback:
-- ALTER TABLE email_accounts DROP COLUMN IF EXISTS auto_send_enabled;

ALTER TABLE email_accounts
    ADD COLUMN IF NOT EXISTS auto_send_enabled BOOLEAN NOT NULL DEFAULT TRUE;
