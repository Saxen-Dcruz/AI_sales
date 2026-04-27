-- Migration 014: Add lead classification fields
-- Rollback: ALTER TABLE leads DROP COLUMN IF EXISTS classification, DROP COLUMN IF EXISTS classification_reason, DROP COLUMN IF EXISTS inbound_first_contact;

ALTER TABLE leads ADD COLUMN IF NOT EXISTS classification VARCHAR DEFAULT 'UNCLASSIFIED';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS classification_reason TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS inbound_first_contact BOOLEAN DEFAULT FALSE;
