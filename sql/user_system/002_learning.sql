-- User system learning schema. Idempotent; execute manually.

CREATE TABLE IF NOT EXISTS user_profiles (
    profile_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_accounts(user_id) ON DELETE CASCADE,
    profile_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS learning_classes (
    class_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_accounts(user_id) ON DELETE CASCADE,
    team_id TEXT NOT NULL,
    learning_goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT learning_classes_status_check CHECK (status IN ('active', 'paused', 'ended', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS learning_progress_records (
    record_id TEXT PRIMARY KEY,
    class_id TEXT NOT NULL REFERENCES learning_classes(class_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES user_accounts(user_id) ON DELETE CASCADE,
    team_id TEXT NOT NULL,
    source_agent TEXT NOT NULL,
    record_type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS learning_summaries (
    summary_id TEXT PRIMARY KEY,
    class_id TEXT NOT NULL REFERENCES learning_classes(class_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES user_accounts(user_id) ON DELETE CASCADE,
    team_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    generated_by TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learning_classes_user_status ON learning_classes (user_id, status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_classes_user_team_status ON learning_classes (user_id, team_id, status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_progress_class_time ON learning_progress_records (user_id, class_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_progress_team_time ON learning_progress_records (team_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_summaries_class_time ON learning_summaries (user_id, class_id, created_at DESC);
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE learning_classes ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
ALTER TABLE learning_progress_records ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
ALTER TABLE learning_summaries ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_learning_classes_active ON learning_classes (user_id, team_id, updated_at DESC) WHERE status IN ('active', 'paused');
