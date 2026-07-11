-- WhatsApp inbound/outbound messages
-- Rollback: DROP TABLE IF EXISTS whatsapp_messages;

DO $$ BEGIN
    CREATE TYPE walabel AS ENUM (
        'Sales','Support','Grievance','Transactional','Promotional','Personal','Unclassified'
    );
EXCEPTION WHEN duplicate_object THEN null;
END $$;
DO $$ BEGIN
    CREATE TYPE wastatus AS ENUM (
        'new','classified','draft_ready','pending_human','replied','archived','ignored'
    );
EXCEPTION WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS whatsapp_messages (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wa_message_id         VARCHAR NOT NULL UNIQUE,
    account_id            UUID REFERENCES whatsapp_accounts(id) ON DELETE SET NULL,
    account_phone         VARCHAR,
    lead_id               UUID REFERENCES leads(id) ON DELETE SET NULL,
    direction             VARCHAR NOT NULL,
    from_number           VARCHAR NOT NULL,
    to_number             VARCHAR NOT NULL,
    body                  TEXT,
    media_url             VARCHAR,
    received_at           TIMESTAMPTZ NOT NULL,
    label                 walabel NOT NULL DEFAULT 'Unclassified',
    status                wastatus NOT NULL DEFAULT 'new',
    classifier_reasoning  TEXT,
    classifier_confidence VARCHAR,
    ai_draft              TEXT,
    followup_gaps         JSON,
    detected_product_id   VARCHAR,
    detected_product_name VARCHAR,
    competitor_mention    VARCHAR,
    needs_human           BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_by           VARCHAR,
    resolved_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wa_messages_account_id  ON whatsapp_messages(account_id);
CREATE INDEX IF NOT EXISTS idx_wa_messages_lead_id     ON whatsapp_messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_wa_messages_label       ON whatsapp_messages(label);
CREATE INDEX IF NOT EXISTS idx_wa_messages_status      ON whatsapp_messages(status);
CREATE INDEX IF NOT EXISTS idx_wa_messages_needs_human ON whatsapp_messages(needs_human) WHERE needs_human = TRUE;
CREATE INDEX IF NOT EXISTS idx_wa_messages_from_number ON whatsapp_messages(from_number);
