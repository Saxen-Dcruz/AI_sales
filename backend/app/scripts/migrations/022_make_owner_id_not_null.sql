-- Phase 1b finalisation: owner_id is now backfilled on every row
-- (default super_admin = saxen@gmail.com), so the column can be made NOT NULL.
-- This is a hard contract — every new row must specify its owner.
--
-- Rollback:
--   ALTER TABLE email_accounts   ALTER COLUMN owner_id DROP NOT NULL;
--   ALTER TABLE leads            ALTER COLUMN owner_id DROP NOT NULL;
--   ALTER TABLE deals            ALTER COLUMN owner_id DROP NOT NULL;
--   ALTER TABLE calls            ALTER COLUMN owner_id DROP NOT NULL;
--   ALTER TABLE calendar_events  ALTER COLUMN owner_id DROP NOT NULL;

ALTER TABLE email_accounts  ALTER COLUMN owner_id SET NOT NULL;
ALTER TABLE leads           ALTER COLUMN owner_id SET NOT NULL;
ALTER TABLE deals           ALTER COLUMN owner_id SET NOT NULL;
ALTER TABLE calls           ALTER COLUMN owner_id SET NOT NULL;
ALTER TABLE calendar_events ALTER COLUMN owner_id SET NOT NULL;
