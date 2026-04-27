-- Migration 009: competitor_mention on emails
-- Rollback: ALTER TABLE emails DROP COLUMN IF EXISTS competitor_mention;
ALTER TABLE emails ADD COLUMN IF NOT EXISTS competitor_mention VARCHAR DEFAULT NULL;
CREATE INDEX IF NOT EXISTS ix_emails_competitor ON emails(competitor_mention) WHERE competitor_mention IS NOT NULL;
