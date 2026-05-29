-- Add rfc_message_id column to emails table.
-- Used for RFC 2822 Message-ID reply threading.
-- Required by Email model in app/models/communication.py.

ALTER TABLE emails ADD COLUMN IF NOT EXISTS rfc_message_id VARCHAR;

CREATE INDEX IF NOT EXISTS ix_emails_rfc_message_id ON emails(rfc_message_id);

-- Rollback:
-- DROP INDEX IF EXISTS ix_emails_rfc_message_id;
-- ALTER TABLE emails DROP COLUMN IF EXISTS rfc_message_id;
