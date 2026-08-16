-- User system exercise schema. Idempotent; execute manually.

CREATE TABLE IF NOT EXISTS exercise_attempts (
    attempt_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_accounts(user_id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES learning_classes(class_id) ON DELETE CASCADE,
    team_id TEXT NOT NULL,
    source_agent TEXT,
    status TEXT NOT NULL DEFAULT 'submitted',
    score NUMERIC,
    max_score NUMERIC,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT exercise_attempts_status_check CHECK (status IN ('started', 'submitted', 'graded', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS exercise_attempt_items (
    item_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES exercise_attempts(attempt_id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    question_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    user_answer JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_correct BOOLEAN,
    score NUMERIC,
    feedback TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_exercise_attempts_user_class_time ON exercise_attempts (user_id, class_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_exercise_attempt_items_attempt ON exercise_attempt_items (attempt_id, created_at ASC);
ALTER TABLE exercise_attempts ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
ALTER TABLE exercise_attempts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE exercise_attempt_items ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_exercise_attempts_active ON exercise_attempts (user_id, class_id, updated_at DESC) WHERE status != 'cancelled';
