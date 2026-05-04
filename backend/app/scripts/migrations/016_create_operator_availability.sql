-- 016: Operator availability and scheduling config
-- Rollback: DROP TABLE scheduling_config; DROP TABLE operator_availability;

CREATE TABLE IF NOT EXISTS operator_availability (
    day_of_week  SMALLINT PRIMARY KEY,   -- 0=Mon … 6=Sun
    is_available BOOLEAN  NOT NULL DEFAULT TRUE,
    start_hour   SMALLINT NOT NULL DEFAULT 9,
    start_minute SMALLINT NOT NULL DEFAULT 0,
    end_hour     SMALLINT NOT NULL DEFAULT 18,
    end_minute   SMALLINT NOT NULL DEFAULT 0
);

-- Seed default Mon-Sat availability (Sunday=6 off by default)
INSERT INTO operator_availability (day_of_week, is_available, start_hour, start_minute, end_hour, end_minute) VALUES
    (0, TRUE,  9, 0, 18, 0),   -- Monday
    (1, TRUE,  9, 0, 18, 0),   -- Tuesday
    (2, TRUE,  9, 0, 18, 0),   -- Wednesday
    (3, TRUE,  9, 0, 18, 0),   -- Thursday
    (4, TRUE,  9, 0, 18, 0),   -- Friday
    (5, TRUE,  9, 0, 14, 0),   -- Saturday (shorter day)
    (6, FALSE, 9, 0, 18, 0)    -- Sunday (unavailable)
ON CONFLICT (day_of_week) DO NOTHING;

CREATE TABLE IF NOT EXISTS scheduling_config (
    id                    SMALLINT PRIMARY KEY DEFAULT 1,
    buffer_minutes        SMALLINT NOT NULL DEFAULT 15,
    slot_duration_minutes SMALLINT NOT NULL DEFAULT 30,
    max_meetings_per_day  SMALLINT NOT NULL DEFAULT 8
);

INSERT INTO scheduling_config (id, buffer_minutes, slot_duration_minutes, max_meetings_per_day)
VALUES (1, 15, 30, 8)
ON CONFLICT (id) DO NOTHING;
