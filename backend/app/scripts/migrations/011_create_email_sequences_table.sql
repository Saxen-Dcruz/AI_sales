-- Migration 011: email drip sequences
-- Rollback: DROP TABLE IF EXISTS email_sequence_steps; DROP TABLE IF EXISTS email_sequences;
CREATE TABLE IF NOT EXISTS email_sequences (
    id          UUID PRIMARY KEY,
    lead_id     UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    name        VARCHAR NOT NULL,
    status      VARCHAR NOT NULL DEFAULT 'active',
    created_by  VARCHAR,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_email_sequences_lead_id ON email_sequences(lead_id);
CREATE INDEX IF NOT EXISTS ix_email_sequences_status  ON email_sequences(status);

CREATE TABLE IF NOT EXISTS email_sequence_steps (
    id             UUID PRIMARY KEY,
    sequence_id    UUID NOT NULL REFERENCES email_sequences(id) ON DELETE CASCADE,
    day_offset     INTEGER NOT NULL,
    subject        VARCHAR NOT NULL,
    body           TEXT NOT NULL,
    status         VARCHAR NOT NULL DEFAULT 'pending',
    send_at        TIMESTAMPTZ NOT NULL,
    sent_at        TIMESTAMPTZ,
    gmail_message_id VARCHAR
);
CREATE INDEX IF NOT EXISTS ix_email_sequence_steps_seq    ON email_sequence_steps(sequence_id);
CREATE INDEX IF NOT EXISTS ix_email_sequence_steps_status ON email_sequence_steps(status, send_at);
