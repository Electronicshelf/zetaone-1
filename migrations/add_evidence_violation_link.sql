-- Add violation_id and evidence_data to evidence table.
-- Add evidence_data to violations table.
-- Run for existing DBs.

-- Violations: add evidence_data if missing
ALTER TABLE violations ADD COLUMN IF NOT EXISTS evidence_data JSONB DEFAULT '{}';

-- Evidence: add violation_id and evidence_data
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS violation_id UUID REFERENCES violations(id);
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS evidence_data JSONB DEFAULT '{}';

-- Migrate content -> evidence_data for existing rows (if content column exists)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='evidence' AND column_name='content') THEN
    -- evidence_data may be json (SQLAlchemy JSON) or jsonb; compare via to_jsonb
    UPDATE evidence
    SET evidence_data = COALESCE(content::jsonb, '{}'::jsonb)
    WHERE evidence_data IS NULL
       OR to_jsonb(evidence_data) = '{}'::jsonb;
  END IF;
END $$;
