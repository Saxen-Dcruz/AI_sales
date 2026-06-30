-- Migration 027: Voice Call Sessions
-- Tracks every AI voice call: origin channel, room, status, escalation, transcript.
-- Reversible: DROP TABLE voice_sessions CASCADE; DROP TABLE voice_call_feedbacks CASCADE;

CREATE TABLE IF NOT EXISTS voice_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_name           VARCHAR(128) NOT NULL UNIQUE,        -- LiveKit room name (UUID-based)
    channel_origin      VARCHAR(16)  NOT NULL,               -- 'whatsapp' | 'gmail' | 'direct'
    channel_ref_id      UUID,                                -- WA message ID or email ID that triggered
    lead_id             UUID REFERENCES leads(id) ON DELETE SET NULL,
    owner_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status              VARCHAR(16)  NOT NULL DEFAULT 'pending',
                        -- pending | active | escalated | completed | expired
    participant_token   TEXT         NOT NULL,               -- short-lived JWT for customer browser
    token_expires_at    TIMESTAMPTZ  NOT NULL,
    joined_at           TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,
    duration_seconds    INTEGER,
    transcript          TEXT,
    ai_summary          TEXT,
    unanswered_count    INTEGER      NOT NULL DEFAULT 0,
    escalation_type     VARCHAR(16)  NOT NULL DEFAULT 'none',
                        -- none | gmeet | office_call
    escalation_ref      TEXT,                                -- GMeet URL or office phone
    feedback_sent       BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_voice_sessions_lead_id     ON voice_sessions(lead_id);
CREATE INDEX IF NOT EXISTS idx_voice_sessions_owner_id    ON voice_sessions(owner_id);
CREATE INDEX IF NOT EXISTS idx_voice_sessions_status      ON voice_sessions(status);
CREATE INDEX IF NOT EXISTS idx_voice_sessions_channel     ON voice_sessions(channel_origin);
CREATE INDEX IF NOT EXISTS idx_voice_sessions_created_at  ON voice_sessions(created_at DESC);
-- Fast lookup for cleanup loop (pending sessions older than 15 min)
CREATE INDEX IF NOT EXISTS idx_voice_sessions_pending_exp ON voice_sessions(token_expires_at)
    WHERE status = 'pending';
