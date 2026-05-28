-- P5: API key table for request authentication.
-- Safe to run multiple times (IF NOT EXISTS guards).

CREATE TABLE IF NOT EXISTS api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    key_hash        VARCHAR(64) NOT NULL UNIQUE,   -- SHA-256 hex; raw key never stored
    prefix          VARCHAR(12) NOT NULL,           -- first 12 chars of raw key (display only)
    name            VARCHAR(255) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_tenant_id  ON api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash   ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active  ON api_keys(is_active) WHERE is_active = TRUE;
