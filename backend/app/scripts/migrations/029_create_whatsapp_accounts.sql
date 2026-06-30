-- WhatsApp Business Cloud API account credentials
-- One row per connected WhatsApp Business phone number.
-- Rollback: DROP TABLE IF EXISTS whatsapp_accounts;

CREATE TABLE IF NOT EXISTS whatsapp_accounts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    phone_number_id  VARCHAR NOT NULL UNIQUE,
    waba_id          VARCHAR NOT NULL,
    access_token     TEXT NOT NULL,
    verify_token     VARCHAR NOT NULL,
    display_phone    VARCHAR NOT NULL,
    display_name     VARCHAR,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    is_primary       BOOLEAN NOT NULL DEFAULT FALSE,
    auto_send        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       VARCHAR DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    updated_at       VARCHAR DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_accounts_owner_id ON whatsapp_accounts(owner_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_accounts_phone_number_id ON whatsapp_accounts(phone_number_id);
