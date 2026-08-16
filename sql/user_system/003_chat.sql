-- User system learning chat schema. Idempotent; execute manually.

CREATE TABLE IF NOT EXISTS learning_chats (
    chat_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_accounts(user_id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES learning_classes(class_id) ON DELETE CASCADE,
    team_id TEXT NOT NULL,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    is_history BOOLEAN NOT NULL DEFAULT false,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    summary_id TEXT REFERENCES learning_summaries(summary_id) ON DELETE SET NULL,
    branch_from_chat_id TEXT REFERENCES learning_chats(chat_id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT learning_chats_status_check CHECK (status IN ('active', 'ended', 'archived', 'deleted'))
);

CREATE TABLE IF NOT EXISTS learning_chat_messages (
    message_id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL REFERENCES learning_chats(chat_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES user_accounts(user_id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES learning_classes(class_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    source_agent TEXT,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT learning_chat_messages_role_check CHECK (role IN ('user', 'assistant', 'system', 'tool'))
);

CREATE INDEX IF NOT EXISTS idx_learning_chats_user_class_time ON learning_chats (user_id, class_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_chats_user_history ON learning_chats (user_id, is_history, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_chat_messages_chat_time ON learning_chat_messages (chat_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_learning_chat_messages_user_class_time ON learning_chat_messages (user_id, class_id, created_at DESC);
ALTER TABLE learning_chats ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
ALTER TABLE learning_chat_messages ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_learning_chats_active ON learning_chats (user_id, class_id, updated_at DESC) WHERE status != 'deleted';
