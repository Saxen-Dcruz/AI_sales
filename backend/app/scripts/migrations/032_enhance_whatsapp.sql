-- WhatsApp Phase 1 enhancements: delivery tracking + templates table
--
-- Rollback:
--   ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS wa_sent_message_id;
--   ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS delivery_status;
--   ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS delivered_at;
--   ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS read_at;
--   ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS failed_reason;
--   ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS message_type;
--   ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS button_reply_id;
--   ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS button_reply_title;
--   ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS list_reply_id;
--   ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS list_reply_title;
--   ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS template_name;
--   DROP TABLE IF EXISTS whatsapp_templates;

-- ── Enhance whatsapp_messages ──────────────────────────────────────────────────
-- Delivery tracking
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS wa_sent_message_id  VARCHAR;
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS delivery_status     VARCHAR DEFAULT 'sent';
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS delivered_at        TIMESTAMPTZ;
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS read_at             TIMESTAMPTZ;
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS failed_reason       VARCHAR;

-- Message sub-type (text/template/button/list/image/document/audio/reaction/location)
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS message_type        VARCHAR DEFAULT 'text';

-- Interactive reply data (populated when direction=inbound and customer replied to buttons/list)
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS button_reply_id     VARCHAR;
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS button_reply_title  VARCHAR;
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS list_reply_id       VARCHAR;
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS list_reply_title    VARCHAR;

-- Template name used to send this message (if type=template)
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS template_name       VARCHAR;

CREATE INDEX IF NOT EXISTS idx_wa_messages_wa_sent_id ON whatsapp_messages(wa_sent_message_id)
  WHERE wa_sent_message_id IS NOT NULL;

-- ── whatsapp_templates ─────────────────────────────────────────────────────────
CREATE TYPE IF NOT EXISTS watemplstatus AS ENUM (
  'PENDING', 'APPROVED', 'REJECTED', 'PAUSED', 'DISABLED', 'IN_APPEAL'
);
CREATE TYPE IF NOT EXISTS watemplcategory AS ENUM (
  'MARKETING', 'UTILITY', 'AUTHENTICATION'
);

CREATE TABLE IF NOT EXISTS whatsapp_templates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    waba_id             VARCHAR NOT NULL,
    account_id          UUID REFERENCES whatsapp_accounts(id) ON DELETE SET NULL,

    -- Meta-assigned ID returned after creation
    meta_template_id    VARCHAR,
    name                VARCHAR NOT NULL,
    language            VARCHAR NOT NULL DEFAULT 'en',
    category            watemplcategory NOT NULL DEFAULT 'UTILITY',
    status              watemplstatus   NOT NULL DEFAULT 'PENDING',
    rejection_reason    TEXT,

    -- Full component definition stored as JSON (same structure sent to Meta)
    components          JSON NOT NULL,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wa_templates_owner_id  ON whatsapp_templates(owner_id);
CREATE INDEX IF NOT EXISTS idx_wa_templates_waba_id   ON whatsapp_templates(waba_id);
CREATE INDEX IF NOT EXISTS idx_wa_templates_status    ON whatsapp_templates(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_wa_templates_name_lang
  ON whatsapp_templates(waba_id, name, language);
