-- Add human_status column to emails table.
-- Tracks what a human has actually done with this thread in the dashboard —
-- independent of `status`, which only reflects AI pipeline progress. An AI
-- auto-reply (no knowledge gaps) flips `status` straight to REPLIED without any
-- human involvement, so `status` alone can't tell "already handled" apart from
-- "nobody has even looked at this yet".
-- Required by Email model in app/models/communication.py (EmailHumanStatus).
--
-- Stored values are the Python enum MEMBER NAMES (UNREAD/READ/REPLIED/RESOLVED),
-- not their lowercase .value — SQLAlchemy's Enum() column type persists/reads
-- .name by default (see the existing `status`/`label` columns, whose native
-- emailstatus/emaillabel Postgres enum types are likewise uppercase), and this
-- plain-VARCHAR column round-trips through that exact same ORM type machinery.

ALTER TABLE emails ADD COLUMN IF NOT EXISTS human_status VARCHAR(10) NOT NULL DEFAULT 'UNREAD';

-- Backfill from existing signals (best-effort — is_read/resolved_by predate this column):
--   resolved_by set  -> a human took final action. approve-draft/manual-send leave
--                       status='REPLIED'; resolve-without-reply also sets resolved_by
--                       but the email may or may not have been replied to directly,
--                       so use status to disambiguate.
--   is_read = true   -> a human opened it but no resolution/reply on record -> READ
--   otherwise        -> default 'UNREAD' stands
UPDATE emails SET human_status = 'REPLIED'
    WHERE resolved_by IS NOT NULL AND status = 'REPLIED';
UPDATE emails SET human_status = 'RESOLVED'
    WHERE resolved_by IS NOT NULL AND status != 'REPLIED' AND human_status = 'UNREAD';
UPDATE emails SET human_status = 'READ'
    WHERE is_read = true AND human_status = 'UNREAD';

CREATE INDEX IF NOT EXISTS ix_emails_human_status ON emails (human_status);

-- Rollback:
-- DROP INDEX IF EXISTS ix_emails_human_status;
-- ALTER TABLE emails DROP COLUMN IF EXISTS human_status;
