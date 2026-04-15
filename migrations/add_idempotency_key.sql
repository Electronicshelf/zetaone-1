-- Add idempotency_key column to assets table.
-- Run this if upgrading from a schema without idempotency support.

-- Add column (no-op if already exists)
ALTER TABLE assets ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255);

-- Unique constraint per tenant (partial index for non-null keys only)
CREATE UNIQUE INDEX IF NOT EXISTS uq_assets_tenant_idempotency
  ON assets (tenant_id, idempotency_key)
  WHERE idempotency_key IS NOT NULL;
