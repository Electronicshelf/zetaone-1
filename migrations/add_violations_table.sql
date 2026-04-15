-- Create violations table for explicit violation storage.
-- Run this if upgrading from a schema without violations.

CREATE TABLE IF NOT EXISTS violations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    signal_id UUID NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    rule_id VARCHAR(128) NOT NULL,
    violation_type VARCHAR(64) NOT NULL,
    severity FLOAT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_violations_asset_id ON violations (asset_id);
CREATE INDEX IF NOT EXISTS ix_violations_signal_id ON violations (signal_id);
CREATE INDEX IF NOT EXISTS ix_violations_rule_id ON violations (rule_id);
CREATE INDEX IF NOT EXISTS ix_violations_violation_type ON violations (violation_type);
