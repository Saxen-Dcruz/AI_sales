-- Migration 015: LinkedIn outreach tracking
-- Rollback: DROP TABLE IF EXISTS linkedin_outreach;

CREATE TABLE IF NOT EXISTS linkedin_outreach (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,
    company_id UUID REFERENCES companies(id) ON DELETE SET NULL,

    -- Profile info captured at discovery time
    linkedin_url VARCHAR UNIQUE,
    full_name VARCHAR,
    headline VARCHAR,
    location VARCHAR,
    company_name VARCHAR,
    role_category VARCHAR,       -- c_suite | cto | operations | procurement | engineering
    industry_tag VARCHAR,        -- which industry bucket we found them under
    city_tag VARCHAR,            -- which city search found them

    -- Connection tracking
    connection_status VARCHAR DEFAULT 'not_sent',  -- not_sent | pending | connected | rejected | withdrawn
    connection_sent_at TIMESTAMPTZ,

    -- Message tracking
    message_status VARCHAR DEFAULT 'not_sent',     -- not_sent | sent | replied | bounced
    message_sent_at TIMESTAMPTZ,
    message_body TEXT,
    message_template_key VARCHAR,                  -- which template was used
    reply_received_at TIMESTAMPTZ,
    reply_preview VARCHAR,

    -- Source
    source VARCHAR DEFAULT 'linkedin_scrape',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_linkedin_outreach_lead_id ON linkedin_outreach(lead_id);
CREATE INDEX IF NOT EXISTS idx_linkedin_outreach_connection_status ON linkedin_outreach(connection_status);
CREATE INDEX IF NOT EXISTS idx_linkedin_outreach_message_status ON linkedin_outreach(message_status);
CREATE INDEX IF NOT EXISTS idx_linkedin_outreach_role_category ON linkedin_outreach(role_category);
CREATE INDEX IF NOT EXISTS idx_linkedin_outreach_industry_tag ON linkedin_outreach(industry_tag);
