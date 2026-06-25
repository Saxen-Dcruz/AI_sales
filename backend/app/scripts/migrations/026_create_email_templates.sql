-- Reusable email templates for Compose and Reply composers.
-- Scoped per user (owner_id); templates with owner_id IS NULL are global/shared (admin-authored).

CREATE TABLE IF NOT EXISTS email_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    subject VARCHAR NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_email_templates_owner_id ON email_templates(owner_id);

-- Rollback:
-- DROP TABLE IF EXISTS email_templates;
