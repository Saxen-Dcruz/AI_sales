-- Migration 034: Voice Call Feedbacks
-- Post-call feedback: rating 1-5 + comment, collected via WA or Gmail.
-- Depends on: 033_create_voice_sessions.sql

CREATE TABLE IF NOT EXISTS voice_call_feedbacks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES voice_sessions(id) ON DELETE CASCADE,
    lead_id         UUID REFERENCES leads(id) ON DELETE SET NULL,
    rating          SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    channel_used    VARCHAR(16) NOT NULL,   -- 'whatsapp' | 'gmail'
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_voice_feedbacks_session_unique ON voice_call_feedbacks(session_id);
CREATE INDEX IF NOT EXISTS idx_voice_feedbacks_lead_id ON voice_call_feedbacks(lead_id);
CREATE INDEX IF NOT EXISTS idx_voice_feedbacks_rating  ON voice_call_feedbacks(rating);
