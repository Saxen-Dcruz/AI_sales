-- Migration 019: Add detected product columns to emails table
-- Stores product matched by the workflow's detect_product node for analytics
-- Rollback: ALTER TABLE emails DROP COLUMN IF EXISTS detected_product_id, DROP COLUMN IF EXISTS detected_product_name;

ALTER TABLE emails ADD COLUMN IF NOT EXISTS detected_product_id VARCHAR;
ALTER TABLE emails ADD COLUMN IF NOT EXISTS detected_product_name VARCHAR;
