-- User system commerce schema. Idempotent; execute manually.

CREATE TABLE IF NOT EXISTS purchase_orders (
    order_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_accounts(user_id) ON DELETE CASCADE,
    product_id TEXT NOT NULL,
    product_type TEXT NOT NULL,
    amount_cents INTEGER NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'CNY',
    status TEXT NOT NULL DEFAULT 'pending',
    paid_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT purchase_orders_status_check CHECK (status IN ('pending', 'paid', 'cancelled', 'refunded'))
);

CREATE TABLE IF NOT EXISTS course_entitlements (
    entitlement_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_accounts(user_id) ON DELETE CASCADE,
    team_id TEXT NOT NULL,
    class_id TEXT REFERENCES learning_classes(class_id) ON DELETE SET NULL,
    order_id TEXT REFERENCES purchase_orders(order_id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active',
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT course_entitlements_status_check CHECK (status IN ('active', 'expired', 'revoked'))
);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_user_status ON purchase_orders (user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_course_entitlements_user_team ON course_entitlements (user_id, team_id, status, starts_at DESC);
ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
ALTER TABLE course_entitlements ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
ALTER TABLE course_entitlements ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_purchase_orders_active ON purchase_orders (user_id, updated_at DESC) WHERE status != 'cancelled';
CREATE INDEX IF NOT EXISTS idx_course_entitlements_active ON course_entitlements (user_id, starts_at DESC) WHERE status != 'revoked';
