-- Extend products table for the richer Add Product form:
-- multi-category/subcategory, FAQs, bulk pricing tiers, variations.

ALTER TABLE products ADD COLUMN IF NOT EXISTS categories JSONB;
ALTER TABLE products ADD COLUMN IF NOT EXISTS subcategories JSONB;
ALTER TABLE products ADD COLUMN IF NOT EXISTS faqs JSONB;
ALTER TABLE products ADD COLUMN IF NOT EXISTS bulk_pricing JSONB;
ALTER TABLE products ADD COLUMN IF NOT EXISTS variations JSONB;

-- Backfill categories/subcategories arrays from the existing single string columns
UPDATE products SET categories = jsonb_build_array(category) WHERE categories IS NULL AND category IS NOT NULL AND category <> '';
UPDATE products SET subcategories = jsonb_build_array(sub_category) WHERE subcategories IS NULL AND sub_category IS NOT NULL AND sub_category <> '';

-- Rollback:
-- ALTER TABLE products DROP COLUMN IF EXISTS categories;
-- ALTER TABLE products DROP COLUMN IF EXISTS subcategories;
-- ALTER TABLE products DROP COLUMN IF EXISTS faqs;
-- ALTER TABLE products DROP COLUMN IF EXISTS bulk_pricing;
-- ALTER TABLE products DROP COLUMN IF EXISTS variations;
