-- Add the Order Information matrix (per-order-code spec/feature comparison) to products.
-- Shape: { "order_codes": [..], "rows": [ { "attribute": str, "values": [str, ...] } ] }
-- values[] is index-aligned to order_codes[].

ALTER TABLE products ADD COLUMN IF NOT EXISTS order_information JSONB;

-- Rollback:
-- ALTER TABLE products DROP COLUMN IF EXISTS order_information;
