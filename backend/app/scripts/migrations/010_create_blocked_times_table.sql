-- Migration 010: recurring availability blocks for calendar scheduling
-- Rollback: DROP TABLE IF EXISTS blocked_times;
CREATE TABLE IF NOT EXISTS blocked_times (
    id           UUID PRIMARY KEY,
    day_of_week  INTEGER NOT NULL,   -- 0=Mon … 5=Sat
    start_hour   INTEGER NOT NULL,
    end_hour     INTEGER NOT NULL,
    label        VARCHAR,
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
