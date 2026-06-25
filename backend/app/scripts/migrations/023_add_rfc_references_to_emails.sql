-- Add rfc_references column to emails table.
-- Used for RFC 2822 References reply threading chain.
-- Required by Email model in app/models/communication.py.

ALTER TABLE emails ADD COLUMN IF NOT EXISTS rfc_references VARCHAR;

-- Rollback:
-- ALTER TABLE emails DROP COLUMN IF EXISTS rfc_references;
