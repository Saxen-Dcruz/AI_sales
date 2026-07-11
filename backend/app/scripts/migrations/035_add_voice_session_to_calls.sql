-- Migration 035: Link calls to voice_sessions
-- Allows querying all calls that originated from a Voice Bridge session.
-- Reversible: ALTER TABLE calls DROP COLUMN IF EXISTS voice_session_id;

ALTER TABLE calls ADD COLUMN IF NOT EXISTS voice_session_id UUID
    REFERENCES voice_sessions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_calls_voice_session_id ON calls(voice_session_id)
    WHERE voice_session_id IS NOT NULL;
