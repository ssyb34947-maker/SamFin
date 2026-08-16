"""PostgreSQL repository for commerce records."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from src.user_system.common.postgres import PostgreSQLStore


class CommerceRepository(Protocol):
    def create_order(self, **payload) -> Dict[str, Any]:
        ...

    def get_order(self, *, order_id: str) -> Optional[Dict[str, Any]]:
        ...

    def list_orders(self, *, user_id: str) -> List[Dict[str, Any]]:
        ...

    def update_order(self, *, order_id: str, status: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...

    def create_entitlement(self, **payload) -> Dict[str, Any]:
        ...

    def get_entitlement(self, *, entitlement_id: str) -> Optional[Dict[str, Any]]:
        ...

    def list_entitlements(self, *, user_id: str) -> List[Dict[str, Any]]:
        ...

    def update_entitlement(self, *, entitlement_id: str, status: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...


class PostgreSQLCommerceRepository:
    def __init__(self, store: PostgreSQLStore):
        self.store = store

    def create_order(self, **payload) -> Dict[str, Any]:
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                INSERT INTO purchase_orders (order_id, user_id, product_id, product_type, amount_cents, currency, metadata)
                VALUES ('order_' || substr(md5(random()::text || clock_timestamp()::text), 1, 12), %s, %s, %s, %s, %s, %s)
                RETURNING order_id, user_id, product_id, product_type, amount_cents, currency, status, paid_at, metadata, created_at, updated_at
                """,
                (
                    payload["user_id"],
                    payload["product_id"],
                    payload["product_type"],
                    payload.get("amount_cents", 0),
                    payload.get("currency", "CNY"),
                    self.store.jsonb(payload.get("metadata") or {}),
                ),
            ).fetchone()
        self.store.delete_cached("orders", payload["user_id"])
        return dict(row)

    def get_order(self, *, order_id: str) -> Optional[Dict[str, Any]]:
        cached = self.store.get_cached_json("order", order_id)
        if cached is not None:
            return cached
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                SELECT order_id, user_id, product_id, product_type, amount_cents, currency, status, paid_at, metadata, created_at, updated_at
                FROM purchase_orders
                WHERE order_id = %s AND status != 'cancelled'
                """,
                (order_id,),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        self.store.set_cached_json(payload, "order", order_id)
        return payload

    def list_orders(self, *, user_id: str) -> List[Dict[str, Any]]:
        cached = self.store.get_cached_json("orders", user_id)
        if cached is not None:
            return list(cached["items"])
        with self.store.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT order_id, user_id, product_id, product_type, amount_cents, currency, status, paid_at, metadata, created_at, updated_at
                FROM purchase_orders
                WHERE user_id = %s AND status != 'cancelled'
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        items = [dict(row) for row in rows]
        self.store.set_cached_json({"items": items}, "orders", user_id)
        return items

    def update_order(self, *, order_id: str, status: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        current = self.get_order(order_id=order_id)
        if current is None:
            raise ValueError("order not found")
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                UPDATE purchase_orders
                SET status = COALESCE(%s, status),
                    paid_at = CASE WHEN %s = 'paid' THEN COALESCE(paid_at, now()) ELSE paid_at END,
                    metadata = COALESCE(%s, metadata),
                    updated_at = now()
                WHERE order_id = %s
                RETURNING order_id, user_id, product_id, product_type, amount_cents, currency, status, paid_at, metadata, created_at, updated_at
                """,
                (status, status, self.store.jsonb(metadata) if metadata is not None else None, order_id),
            ).fetchone()
        if row is None:
            raise ValueError("order not found")
        self.store.delete_cached("order", order_id)
        self.store.delete_cached("orders", current["user_id"])
        return dict(row)

    def create_entitlement(self, **payload) -> Dict[str, Any]:
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                INSERT INTO course_entitlements (entitlement_id, user_id, team_id, class_id, order_id, metadata)
                VALUES ('ent_' || substr(md5(random()::text || clock_timestamp()::text), 1, 12), %s, %s, %s, %s, %s)
                RETURNING entitlement_id, user_id, team_id, class_id, order_id, status, starts_at, expires_at, metadata, created_at
                """,
                (
                    payload["user_id"],
                    payload["team_id"],
                    payload.get("class_id"),
                    payload.get("order_id"),
                    self.store.jsonb(payload.get("metadata") or {}),
                ),
            ).fetchone()
        self.store.delete_cached("entitlements", payload["user_id"])
        return dict(row)

    def get_entitlement(self, *, entitlement_id: str) -> Optional[Dict[str, Any]]:
        cached = self.store.get_cached_json("entitlement", entitlement_id)
        if cached is not None:
            return cached
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                SELECT entitlement_id, user_id, team_id, class_id, order_id, status, starts_at, expires_at, metadata, created_at
                FROM course_entitlements
                WHERE entitlement_id = %s AND status != 'revoked'
                """,
                (entitlement_id,),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        self.store.set_cached_json(payload, "entitlement", entitlement_id)
        return payload

    def list_entitlements(self, *, user_id: str) -> List[Dict[str, Any]]:
        cached = self.store.get_cached_json("entitlements", user_id)
        if cached is not None:
            return list(cached["items"])
        with self.store.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT entitlement_id, user_id, team_id, class_id, order_id, status, starts_at, expires_at, metadata, created_at
                FROM course_entitlements
                WHERE user_id = %s AND status != 'revoked'
                ORDER BY starts_at DESC
                """,
                (user_id,),
            ).fetchall()
        items = [dict(row) for row in rows]
        self.store.set_cached_json({"items": items}, "entitlements", user_id)
        return items

    def update_entitlement(self, *, entitlement_id: str, status: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        current = self.get_entitlement(entitlement_id=entitlement_id)
        if current is None:
            raise ValueError("entitlement not found")
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                UPDATE course_entitlements
                SET status = COALESCE(%s, status),
                    metadata = COALESCE(%s, metadata)
                WHERE entitlement_id = %s
                RETURNING entitlement_id, user_id, team_id, class_id, order_id, status, starts_at, expires_at, metadata, created_at
                """,
                (status, self.store.jsonb(metadata) if metadata is not None else None, entitlement_id),
            ).fetchone()
        if row is None:
            raise ValueError("entitlement not found")
        self.store.delete_cached("entitlement", entitlement_id)
        self.store.delete_cached("entitlements", current["user_id"])
        return dict(row)
