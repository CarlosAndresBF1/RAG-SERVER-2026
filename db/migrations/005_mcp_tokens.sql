CREATE TABLE IF NOT EXISTS mcp_token (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100)  NOT NULL,           -- Descriptive name ("Carlos - VS Code")
    token_hash      VARCHAR(255)  NOT NULL,           -- SHA-256 of the token (never store raw)
    token_prefix    VARCHAR(12)   NOT NULL,           -- First 8 chars for identification ("odr_a1b2...")
    issued_by       UUID          NOT NULL REFERENCES admin_user(id),
    scopes          VARCHAR[]     NOT NULL DEFAULT ARRAY['read'],  -- read, write, ingest
    is_active       BOOLEAN       DEFAULT TRUE,
    expires_at      TIMESTAMPTZ,                      -- NULL = no expiry
    last_used_at    TIMESTAMPTZ,
    usage_count     INTEGER       DEFAULT 0,
    rate_limit_rpm  INTEGER       DEFAULT 60,         -- Requests per minute
    created_at      TIMESTAMPTZ   DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ                       -- NULL = active
);

CREATE INDEX IF NOT EXISTS idx_mcp_token_hash   ON mcp_token (token_hash) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_mcp_token_prefix ON mcp_token (token_prefix);

-- Audit log
CREATE TABLE IF NOT EXISTS mcp_token_audit (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token_id    UUID         NOT NULL REFERENCES mcp_token(id),
    action      VARCHAR(20)  NOT NULL,  -- created, used, revoked, expired
    ip_address  INET,
    user_agent  VARCHAR(500),
    tool_name   VARCHAR(100),           -- Which MCP tool was called
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mcp_audit_token   ON mcp_token_audit (token_id);
CREATE INDEX IF NOT EXISTS idx_mcp_audit_created ON mcp_token_audit (created_at DESC);
