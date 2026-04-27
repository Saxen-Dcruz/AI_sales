-- Migration 004: Create emails table for Gmail intelligence pipeline
-- Rollback: DROP TABLE IF EXISTS emails; DROP TYPE IF EXISTS emaillabel; DROP TYPE IF EXISTS emailstatus;

CREATE TYPE emaillabel AS ENUM (
    'Sales', 'Support', 'Grievance', 'Transactional', 'Promotional', 'Personal', 'Unclassified'
);

CREATE TYPE emailstatus AS ENUM (
    'new', 'classified', 'draft_ready', 'pending_human', 'replied', 'archived', 'ignored'
);

CREATE TABLE IF NOT EXISTS emails (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gmail_message_id        VARCHAR NOT NULL,
    gmail_thread_id         VARCHAR,
    lead_id                 UUID REFERENCES leads(id) ON DELETE SET NULL,

    direction               VARCHAR NOT NULL,
    sender                  VARCHAR NOT NULL,
    recipients              JSONB NOT NULL DEFAULT '[]',
    subject                 VARCHAR,
    body_text               TEXT,
    body_html               TEXT,
    received_at             TIMESTAMPTZ NOT NULL,

    label                   emaillabel NOT NULL DEFAULT 'Unclassified',
    status                  emailstatus NOT NULL DEFAULT 'new',

    classifier_reasoning    TEXT,
    classifier_confidence   VARCHAR,

    transactional_type      VARCHAR,
    transactional_data      JSONB,

    ai_draft                TEXT,
    gmail_draft_id          VARCHAR,

    needs_human             BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_by             VARCHAR,
    resolved_at             TIMESTAMPTZ,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_emails_gmail_message_id ON emails(gmail_message_id);
CREATE INDEX IF NOT EXISTS idx_emails_lead_id ON emails(lead_id);
CREATE INDEX IF NOT EXISTS idx_emails_label ON emails(label);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
CREATE INDEX IF NOT EXISTS idx_emails_needs_human ON emails(needs_human) WHERE needs_human = TRUE;
CREATE INDEX IF NOT EXISTS idx_emails_gmail_thread_id ON emails(gmail_thread_id);
