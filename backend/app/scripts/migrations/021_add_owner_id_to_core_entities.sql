-- Phase 1a of RBAC / "god mode" super-admin rollout.
-- Adds nullable owner_id FK → users(id) on the five core entities so each row
-- can be attributed to the app user who owns it. Phase 1b (separate migration
-- after super_admin is seeded) backfills NULL → super_admin and flips columns
-- to NOT NULL.
--
-- Rollback:
--   ALTER TABLE email_accounts   DROP COLUMN IF EXISTS owner_id;
--   ALTER TABLE leads            DROP COLUMN IF EXISTS owner_id;
--   ALTER TABLE deals            DROP COLUMN IF EXISTS owner_id;
--   ALTER TABLE calls            DROP COLUMN IF EXISTS owner_id;
--   ALTER TABLE calendar_events  DROP COLUMN IF EXISTS owner_id;

ALTER TABLE email_accounts
    ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_email_accounts_owner_id ON email_accounts(owner_id);

ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_leads_owner_id ON leads(owner_id);

ALTER TABLE deals
    ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_deals_owner_id ON deals(owner_id);

ALTER TABLE calls
    ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_calls_owner_id ON calls(owner_id);

ALTER TABLE calendar_events
    ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_calendar_events_owner_id ON calendar_events(owner_id);
