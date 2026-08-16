"""PostgreSQL repository for exercise attempts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from src.user_system.common.postgres import PostgreSQLStore


class ExerciseRepository(Protocol):
    def create_exercise_attempt(self, *, user_id: str, class_id: str, team_id: str, source_agent: Optional[str], items: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def get_exercise_attempt(self, *, attempt_id: str) -> Optional[Dict[str, Any]]:
        ...

    def list_exercise_attempts(self, *, user_id: str, class_id: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    def update_attempt(self, *, attempt_id: str, status: Optional[str] = None, score: Optional[float] = None, max_score: Optional[float] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...

    def archive_attempt(self, *, attempt_id: str) -> Dict[str, Any]:
        ...


class PostgreSQLExerciseRepository:
    def __init__(self, store: PostgreSQLStore):
        self.store = store

    def create_exercise_attempt(self, *, user_id: str, class_id: str, team_id: str, source_agent: Optional[str], items: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
        with self.store.pool.connection() as conn:
            with conn.transaction():
                attempt = conn.execute(
                    """
                    INSERT INTO exercise_attempts (attempt_id, user_id, class_id, team_id, source_agent, status, submitted_at, metadata)
                    VALUES ('attempt_' || substr(md5(random()::text || clock_timestamp()::text), 1, 12), %s, %s, %s, %s, 'submitted', now(), %s)
                    RETURNING attempt_id, user_id, class_id, team_id, source_agent, status, score, max_score, started_at, submitted_at, metadata
                    """,
                    (user_id, class_id, team_id, source_agent, self.store.jsonb(metadata)),
                ).fetchone()
                for item in items:
                    conn.execute(
                        """
                        INSERT INTO exercise_attempt_items (item_id, attempt_id, question_id, question_snapshot, user_answer, is_correct, score, feedback)
                        VALUES ('item_' || substr(md5(random()::text || clock_timestamp()::text), 1, 12), %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            attempt["attempt_id"],
                            item.get("question_id", ""),
                            self.store.jsonb(item.get("question_snapshot", {})),
                            self.store.jsonb(item.get("user_answer", {})),
                            item.get("is_correct"),
                            item.get("score"),
                            item.get("feedback"),
                        ),
                    )
        self.store.delete_cached_pattern("attempts", user_id, "*")
        return self.get_exercise_attempt(attempt_id=attempt["attempt_id"])

    def get_exercise_attempt(self, *, attempt_id: str) -> Optional[Dict[str, Any]]:
        cached = self.store.get_cached_json("attempt", attempt_id)
        if cached is not None:
            return cached
        with self.store.pool.connection() as conn:
            attempt = conn.execute(
                """
                SELECT attempt_id, user_id, class_id, team_id, source_agent, status, score, max_score, started_at, submitted_at, metadata
                FROM exercise_attempts
                WHERE attempt_id = %s AND status != 'cancelled'
                """,
                (attempt_id,),
            ).fetchone()
            if attempt is None:
                return None
            items = conn.execute(
                """
                SELECT item_id, attempt_id, question_id, question_snapshot, user_answer, is_correct, score, feedback, created_at
                FROM exercise_attempt_items
                WHERE attempt_id = %s
                ORDER BY created_at ASC
                """,
                (attempt_id,),
            ).fetchall()
        payload = dict(attempt)
        payload["items"] = [dict(item) for item in items]
        self.store.set_cached_json(payload, "attempt", attempt_id)
        return payload

    def list_exercise_attempts(self, *, user_id: str, class_id: Optional[str] = None) -> List[Dict[str, Any]]:
        class_key = class_id or "all"
        cached = self.store.get_cached_json("attempts", user_id, class_key)
        if cached is not None:
            return list(cached["items"])
        class_filter = "" if class_id is None else "AND class_id = %s"
        params = (user_id,) if class_id is None else (user_id, class_id)
        with self.store.pool.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT attempt_id, user_id, class_id, team_id, source_agent, status, score, max_score, started_at, submitted_at, metadata
                FROM exercise_attempts
                WHERE user_id = %s AND status != 'cancelled' {class_filter}
                ORDER BY started_at DESC
                """,
                params,
            ).fetchall()
        items = [dict(row) for row in rows]
        self.store.set_cached_json({"items": items}, "attempts", user_id, class_key)
        return items

    def update_attempt(self, *, attempt_id: str, status: Optional[str] = None, score: Optional[float] = None, max_score: Optional[float] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        current = self.get_exercise_attempt(attempt_id=attempt_id)
        if current is None:
            raise ValueError("attempt not found")
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                UPDATE exercise_attempts
                SET status = COALESCE(%s, status),
                    score = COALESCE(%s, score),
                    max_score = COALESCE(%s, max_score),
                    metadata = COALESCE(%s, metadata),
                    submitted_at = CASE WHEN %s IN ('submitted', 'graded') THEN COALESCE(submitted_at, now()) ELSE submitted_at END
                WHERE attempt_id = %s
                RETURNING attempt_id
                """,
                (status, score, max_score, self.store.jsonb(metadata) if metadata is not None else None, status, attempt_id),
            ).fetchone()
        if row is None:
            raise ValueError("attempt not found")
        self.store.delete_cached("attempt", attempt_id)
        self.store.delete_cached_pattern("attempts", current["user_id"], "*")
        return self.get_exercise_attempt(attempt_id=attempt_id)

    def archive_attempt(self, *, attempt_id: str) -> Dict[str, Any]:
        return self.update_attempt(attempt_id=attempt_id, status="cancelled")
