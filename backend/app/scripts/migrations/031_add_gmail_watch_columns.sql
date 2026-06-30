-- Gmail Push Notifications (Pub/Sub) — per-account watch state
-- watch_history_id : the historyId from the last users.watch() call; used
--                    as the startHistoryId when listing new messages after
--                    a Pub/Sub notification arrives.
-- watch_expiry     : when the watch expires (7 days from registration).
--                    The startup/renewal loop renews when < 24h remains.
--
-- Rollback:
--   ALTER TABLE email_accounts DROP COLUMN IF EXISTS watch_history_id;
--   ALTER TABLE email_accounts DROP COLUMN IF EXISTS watch_expiry;

ALTER TABLE email_accounts ADD COLUMN IF NOT EXISTS watch_history_id VARCHAR;
ALTER TABLE email_accounts ADD COLUMN IF NOT EXISTS watch_expiry TIMESTAMPTZ;
