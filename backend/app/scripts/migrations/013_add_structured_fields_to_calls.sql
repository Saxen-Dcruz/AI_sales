-- Migration 013: Add structured extraction fields to calls table
-- Rollback: ALTER TABLE calls DROP COLUMN IF EXISTS intent, DROP COLUMN IF EXISTS urgency, DROP COLUMN IF EXISTS product_interest;

ALTER TABLE calls ADD COLUMN IF NOT EXISTS intent VARCHAR;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS urgency VARCHAR;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS product_interest VARCHAR;
