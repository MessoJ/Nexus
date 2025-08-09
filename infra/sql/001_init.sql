CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS content_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_url TEXT,
    title TEXT,
    source_metadata JSONB DEFAULT '{}',
    article_text TEXT,
    analysis_json JSONB,
    script_text TEXT,
    media_url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_content_jobs_status ON content_jobs(status);
CREATE INDEX IF NOT EXISTS idx_content_jobs_created_at ON content_jobs(created_at);

CREATE TABLE IF NOT EXISTS ingested_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_key TEXT NOT NULL UNIQUE,
    source_url TEXT,
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger to keep updated_at fresh
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_updated_at ON content_jobs;
CREATE TRIGGER trg_set_updated_at
BEFORE UPDATE ON content_jobs
FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

