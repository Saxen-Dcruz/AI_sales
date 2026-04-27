-- Migration 008: calls table
-- Logs inbound and outbound sales calls.
-- Shares gap detection logic with the email pipeline (sales_gap_service.py).
-- Rollback: DROP TABLE IF EXISTS calls;

CREATE TABLE IF NOT EXISTS calls (
    id                    UUID PRIMARY KEY,
    lead_id               UUID REFERENCES leads(id) ON DELETE SET NULL,

    direction             VARCHAR NOT NULL,
    status                VARCHAR NOT NULL DEFAULT 'new',
    outcome               VARCHAR,

    phone_number          VARCHAR,
    livekit_room          VARCHAR,
    recording_url         VARCHAR,

    started_at            TIMESTAMPTZ,
    ended_at              TIMESTAMPTZ,
    duration_seconds      INTEGER DEFAULT 0,

    transcript            TEXT,
    ai_summary            TEXT,
    sentiment             VARCHAR,

    detected_product_id   VARCHAR,
    detected_product_name VARCHAR,
    followup_gaps         JSON,

    handled_by            VARCHAR,
    notes                 TEXT,

    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_calls_lead_id   ON calls(lead_id);
CREATE INDEX IF NOT EXISTS ix_calls_status    ON calls(status);
CREATE INDEX IF NOT EXISTS ix_calls_direction ON calls(direction);
