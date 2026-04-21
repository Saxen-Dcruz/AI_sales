-- Migration 002: Create users table for JWT auth
-- Apply:   docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -f /migrations/002_create_users_table.sql
-- Rollback: see bottom of file

CREATE TABLE IF NOT EXISTS users (
    id               SERIAL PRIMARY KEY,
    email            VARCHAR NOT NULL UNIQUE,
    hashed_password  VARCHAR NOT NULL,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- Rollback
-- DROP TABLE IF EXISTS users;
