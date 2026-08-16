-- User system auth schema. Idempotent; execute manually.

CREATE TABLE IF NOT EXISTS user_accounts (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE,
    email TEXT UNIQUE,
    display_name TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    roles TEXT[] NOT NULL DEFAULT ARRAY['student'],
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT user_accounts_status_check CHECK (status IN ('active', 'disabled', 'deleted'))
);

CREATE TABLE IF NOT EXISTS user_credentials (
    user_id TEXT PRIMARY KEY REFERENCES user_accounts(user_id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL,
    password_algorithm TEXT NOT NULL DEFAULT 'argon2id',
    password_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auth_refresh_tokens (
    token_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_accounts(user_id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    jwt_id TEXT NOT NULL UNIQUE,
    device_id TEXT,
    user_agent TEXT,
    ip_address TEXT,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    replaced_by_token_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS auth_login_events (
    event_id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES user_accounts(user_id) ON DELETE SET NULL,
    identifier TEXT,
    success BOOLEAN NOT NULL,
    failure_reason TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_accounts_email ON user_accounts (lower(email)) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_accounts_username ON user_accounts (lower(username)) WHERE username IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_user_active ON auth_refresh_tokens (user_id, expires_at DESC) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_jti ON auth_refresh_tokens (jwt_id);
CREATE INDEX IF NOT EXISTS idx_auth_login_events_identifier_time ON auth_login_events (identifier, created_at DESC);
ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE auth_refresh_tokens ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_user_accounts_active ON user_accounts (status, updated_at DESC) WHERE status != 'deleted';
