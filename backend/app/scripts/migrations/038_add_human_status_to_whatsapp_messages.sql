-- Add human_status column to whatsapp_messages table.
-- Tracks what a human has actually done with this message in the dashboard —
-- independent of `status`, which only reflects AI pipeline progress. See
-- 037_add_human_status_to_emails.sql for the Gmail counterpart and full rationale
-- (including why stored values are uppercase enum member NAMES, e.g. 'REPLIED',
-- not the lowercase .value).
-- Required by WhatsAppMessage model in app/models/whatsapp_message.py (WAHumanStatus).

ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS human_status VARCHAR(10) NOT NULL DEFAULT 'UNREAD';

-- Backfill from existing signals (best-effort — there's no WhatsApp equivalent of
-- Gmail's is_read to backfill a "read but not actioned" state from, so anything
-- without a clear resolved_by/replied signal simply stays at the 'UNREAD' default):
UPDATE whatsapp_messages SET human_status = 'REPLIED'
    WHERE resolved_by IS NOT NULL AND status = 'REPLIED';
UPDATE whatsapp_messages SET human_status = 'RESOLVED'
    WHERE resolved_by IS NOT NULL AND status != 'REPLIED' AND human_status = 'UNREAD';

CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_human_status ON whatsapp_messages (human_status);

-- Rollback:
-- DROP INDEX IF EXISTS ix_whatsapp_messages_human_status;
-- ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS human_status;
