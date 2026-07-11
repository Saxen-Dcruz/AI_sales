-- Add is_read column to emails table.
-- Tracks whether a human has opened the email in the dashboard, independent of
-- its workflow `status` (which only reflects AI pipeline progress, not human viewing).
-- Required by Email model in app/models/communication.py.

ALTER TABLE emails ADD COLUMN IF NOT EXISTS is_read BOOLEAN NOT NULL DEFAULT FALSE;

-- Rollback:
-- ALTER TABLE emails DROP COLUMN IF EXISTS is_read;
