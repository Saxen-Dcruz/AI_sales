-- Add open-tracking fields to emails table.
-- tracking_token is embedded in the pixel URL of outbound emails; opened_at/open_count
-- are updated when the recipient mail client loads that pixel.

ALTER TABLE emails ADD COLUMN IF NOT EXISTS tracking_token UUID UNIQUE;
ALTER TABLE emails ADD COLUMN IF NOT EXISTS opened_at TIMESTAMPTZ;
ALTER TABLE emails ADD COLUMN IF NOT EXISTS open_count INTEGER NOT NULL DEFAULT 0;

-- Rollback:
-- ALTER TABLE emails DROP COLUMN IF EXISTS tracking_token;
-- ALTER TABLE emails DROP COLUMN IF EXISTS opened_at;
-- ALTER TABLE emails DROP COLUMN IF EXISTS open_count;
