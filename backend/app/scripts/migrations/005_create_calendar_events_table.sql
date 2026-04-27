-- Migration 005: Create calendar_events table
-- Rollback: DROP TABLE IF EXISTS calendar_events; DROP TYPE IF EXISTS eventtrigger; DROP TYPE IF EXISTS eventstatus;

CREATE TYPE eventtrigger AS ENUM ('deal_signal', 'rag_insufficient', 'manual');
CREATE TYPE eventstatus AS ENUM ('scheduled', 'cancelled', 'completed');

CREATE TABLE IF NOT EXISTS calendar_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_event_id     VARCHAR UNIQUE,
    lead_id             UUID REFERENCES leads(id) ON DELETE SET NULL,
    deal_id             UUID REFERENCES deals(id) ON DELETE SET NULL,

    title               VARCHAR NOT NULL,
    description         TEXT,
    attendee_email      VARCHAR NOT NULL,

    start_time          TIMESTAMPTZ NOT NULL,
    end_time            TIMESTAMPTZ NOT NULL,

    meet_link           VARCHAR,
    calendar_link       VARCHAR,

    trigger             eventtrigger NOT NULL,
    status              eventstatus NOT NULL DEFAULT 'scheduled',
    invite_email_sent   BOOLEAN NOT NULL DEFAULT FALSE,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_lead_id ON calendar_events(lead_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_deal_id ON calendar_events(deal_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_status ON calendar_events(status);
