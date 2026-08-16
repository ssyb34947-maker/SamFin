"""PostgreSQL repository for user profiles and learning classes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from src.user_system.common.postgres import PostgreSQLStore


class ProfileRepository(Protocol):
    def upsert_profile(self, *, user_id: str, profile: Dict[str, Any], display_name: Optional[str] = None) -> Dict[str, Any]:
        ...

    def get_profile(self, *, user_id: str) -> Dict[str, Any]:
        ...

    def create_class(self, *, user_id: str, team_id: str, learning_goal: str, class_id: Optional[str] = None) -> Dict[str, Any]:
        ...

    def get_class(self, *, user_id: str, class_id: str) -> Optional[Dict[str, Any]]:
        ...

    def list_classes(self, *, user_id: str, status: str = "active") -> List[Dict[str, Any]]:
        ...

    def update_class(self, *, user_id: str, class_id: str, learning_goal: Optional[str] = None, status: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...

    def archive_class(self, *, user_id: str, class_id: str) -> Dict[str, Any]:
        ...


class PostgreSQLProfileRepository:
    def __init__(self, store: PostgreSQLStore):
        self.store = store

    def upsert_profile(self, *, user_id: str, profile: Dict[str, Any], display_name: Optional[str] = None) -> Dict[str, Any]:
        with self.store.pool.connection() as conn:
            with conn.transaction():
                conn.execute("INSERT INTO user_accounts (user_id, display_name) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET display_name = COALESCE(EXCLUDED.display_name, user_accounts.display_name), updated_at = now()", (user_id, display_name))
                row = conn.execute(
                    """
                    INSERT INTO user_profiles (profile_id, user_id, profile_json)
                    VALUES ('profile_' || substr(md5(random()::text || clock_timestamp()::text), 1, 12), %s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET profile_json = EXCLUDED.profile_json, updated_at = now()
                    RETURNING profile_id, user_id, profile_json, created_at, updated_at
                    """,
                    (user_id, self.store.jsonb(profile)),
                ).fetchone()
        self.store.delete_cached("profile", user_id)
        return dict(row)

    def get_profile(self, *, user_id: str) -> Dict[str, Any]:
        cached = self.store.get_cached_json("profile", user_id)
        if cached is not None:
            return cached
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                SELECT ua.user_id, ua.username, ua.email, ua.display_name, ua.status, ua.roles,
                       COALESCE(up.profile_json, '{}'::jsonb) AS profile
                FROM user_accounts ua
                LEFT JOIN user_profiles up ON up.user_id = ua.user_id
                WHERE ua.user_id = %s AND ua.status != 'deleted'
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            raise ValueError("user not found")
        payload = dict(row)
        self.store.set_cached_json(payload, "profile", user_id)
        return payload

    def create_class(self, *, user_id: str, team_id: str, learning_goal: str, class_id: Optional[str] = None) -> Dict[str, Any]:
        with self.store.pool.connection() as conn:
            with conn.transaction():
                conn.execute("INSERT INTO user_accounts (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (user_id,))
                row = conn.execute(
                    """
                    INSERT INTO learning_classes (class_id, user_id, team_id, learning_goal)
                    VALUES (COALESCE(%s, 'class_' || substr(md5(random()::text || clock_timestamp()::text), 1, 12)), %s, %s, %s)
                    RETURNING class_id, user_id, team_id, learning_goal, status, started_at, ended_at, metadata, created_at, updated_at
                    """,
                    (class_id, user_id, team_id, learning_goal),
                ).fetchone()
        self.store.delete_cached_pattern("classes", user_id, "*")
        return dict(row)

    def get_class(self, *, user_id: str, class_id: str) -> Optional[Dict[str, Any]]:
        cached = self.store.get_cached_json("class", user_id, class_id)
        if cached is not None:
            return cached
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                SELECT class_id, user_id, team_id, learning_goal, status, started_at, ended_at, metadata, created_at, updated_at
                FROM learning_classes
                WHERE user_id = %s AND class_id = %s AND status != 'cancelled'
                """,
                (user_id, class_id),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        self.store.set_cached_json(payload, "class", user_id, class_id)
        return payload

    def list_classes(self, *, user_id: str, status: str = "active") -> List[Dict[str, Any]]:
        cached = self.store.get_cached_json("classes", user_id, status)
        if cached is not None:
            return list(cached["items"])
        where_status = "" if status == "all" else "AND status = %s"
        params = (user_id,) if status == "all" else (user_id, status)
        with self.store.pool.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT class_id, user_id, team_id, learning_goal, status, started_at, ended_at, metadata, created_at, updated_at
                FROM learning_classes
                WHERE user_id = %s {where_status}
                ORDER BY started_at DESC
                """,
                params,
            ).fetchall()
        items = [dict(row) for row in rows]
        self.store.set_cached_json({"items": items}, "classes", user_id, status)
        return items

    def update_class(self, *, user_id: str, class_id: str, learning_goal: Optional[str] = None, status: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                UPDATE learning_classes
                SET learning_goal = COALESCE(%s, learning_goal),
                    status = COALESCE(%s, status),
                    metadata = COALESCE(%s, metadata),
                    ended_at = CASE WHEN %s IN ('ended', 'cancelled') THEN now() ELSE ended_at END,
                    updated_at = now()
                WHERE user_id = %s AND class_id = %s
                RETURNING class_id, user_id, team_id, learning_goal, status, started_at, ended_at, metadata, created_at, updated_at
                """,
                (learning_goal, status, self.store.jsonb(metadata) if metadata is not None else None, status, user_id, class_id),
            ).fetchone()
        if row is None:
            raise ValueError("class not found")
        self.store.delete_cached("class", user_id, class_id)
        self.store.delete_cached_pattern("classes", user_id, "*")
        self.store.delete_cached("learning_context", user_id, class_id)
        return dict(row)

    def archive_class(self, *, user_id: str, class_id: str) -> Dict[str, Any]:
        return self.update_class(user_id=user_id, class_id=class_id, status="cancelled")
