-- Migration 012: knowledge coverage score per product
-- coverage_score = % of gaps that have been resolved for this product (0–100)
-- Rollback: ALTER TABLE products DROP COLUMN IF EXISTS coverage_score;
ALTER TABLE products ADD COLUMN IF NOT EXISTS coverage_score FLOAT DEFAULT NULL;
