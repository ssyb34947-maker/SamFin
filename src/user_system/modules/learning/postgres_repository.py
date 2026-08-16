"""
PostgreSQL repository for user learning context.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from src.user_system.common.postgres import PostgreSQLStore
from src.user_system.common.schema_check import required_table_names
from .schemas import LearningClass, LearningContextBundle, LearningProgressRecord, LearningSummary


def _metadata(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(value or {})


class PostgreSQLUserLearningRepository:

    REQUIRED_TABLES = required_table_names()


    def __init__(self, *, store: PostgreSQLStore):
        self.store = store
        self.cache = store.cache
        self._jsonb = store.jsonb
        self._pool = store.pool


    def list_existing_tables(self, table_names) -> set[str]:
        return self.store.list_existing_tables(table_names)

    def verify_schema_ready(self) -> None:
        self.store.verify_schema_ready()

    def get_or_create_user(
        self,
        *,
        user_id: str,
        username: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._pool.connection() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    INSERT INTO user_accounts (user_id, username, email)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET updated_at = now()
                    RETURNING user_id, username, email, display_name, status, created_at, updated_at
                    """,
                    (user_id, username, email),
                ).fetchone()
                return dict(row)

    def get_or_create_class(self, *, user_id: str, class_id: str, team_id: str, learning_goal: str) -> LearningClass:
        self.get_or_create_user(user_id=user_id)
        with self._pool.connection() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    INSERT INTO learning_classes (class_id, user_id, team_id, learning_goal)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (class_id) DO UPDATE
                    SET updated_at = now()
                    RETURNING class_id, user_id, team_id, learning_goal, status, started_at, ended_at
                    """,
                    (class_id, user_id, team_id, learning_goal),
                ).fetchone()
                return self._class_from_row(row)

    def get_context(self, *, user_id: str, class_id: str, team_id: str, recent_limit: int = 8) -> LearningContextBundle:
        if self.cache is not None:
            cached = self.cache.get_json(self.cache.learning_context_key(user_id=user_id, class_id=class_id))
            if cached is not None:
                return self._bundle_from_dict(cached)

        learning_class = self.get_or_create_class(
            user_id=user_id,
            class_id=class_id,
            team_id=team_id,
            learning_goal=team_id,
        )
        with self._pool.connection() as conn:
            records = conn.execute(
                """
                SELECT record_id, class_id, user_id, team_id, source_agent, record_type, content, metadata, created_at
                FROM learning_progress_records
                WHERE user_id = %s AND class_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, class_id, recent_limit),
            ).fetchall()
            summaries = conn.execute(
                """
                SELECT summary_id, class_id, user_id, team_id, summary, generated_by, created_at
                FROM learning_summaries
                WHERE user_id = %s AND class_id = %s
                ORDER BY created_at DESC
                LIMIT 3
                """,
                (user_id, class_id),
            ).fetchall()

        bundle = LearningContextBundle(
            learning_class=learning_class,
            recent_records=[self._record_from_row(row) for row in reversed(records)],
            summaries=[self._summary_from_row(row) for row in reversed(summaries)],
        )
        if self.cache is not None:
            self.cache.set_json(self.cache.learning_context_key(user_id=user_id, class_id=class_id), bundle.to_dict())
        return bundle

    def append_progress_record(
        self,
        *,
        user_id: str,
        class_id: str,
        team_id: str,
        source_agent: str,
        record_type: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> LearningProgressRecord:
        with self._pool.connection() as conn:
            with conn.transaction():
                self._lock_class(conn, user_id=user_id, class_id=class_id, team_id=team_id)
                row = conn.execute(
                    """
                    INSERT INTO learning_progress_records
                    (record_id, class_id, user_id, team_id, source_agent, record_type, content, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING record_id, class_id, user_id, team_id, source_agent, record_type, content, metadata, created_at
                    """,
                    (
                        f"lpr_{uuid.uuid4().hex[:12]}",
                        class_id,
                        user_id,
                        team_id,
                        source_agent,
                        record_type,
                        content,
                        self._jsonb(_metadata(metadata)),
                    ),
                ).fetchone()
        self._invalidate_context(user_id=user_id, class_id=class_id)
        return self._record_from_row(row)

    def save_summary(
        self,
        *,
        user_id: str,
        class_id: str,
        team_id: str,
        summary: str,
        generated_by: str,
    ) -> LearningSummary:
        with self._pool.connection() as conn:
            with conn.transaction():
                self._lock_class(conn, user_id=user_id, class_id=class_id, team_id=team_id)
                row = conn.execute(
                    """
                    INSERT INTO learning_summaries (summary_id, class_id, user_id, team_id, summary, generated_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING summary_id, class_id, user_id, team_id, summary, generated_by, created_at
                    """,
                    (f"ls_{uuid.uuid4().hex[:12]}", class_id, user_id, team_id, summary, generated_by),
                ).fetchone()
        self._invalidate_context(user_id=user_id, class_id=class_id)
        return self._summary_from_row(row)

    def end_class(self, *, user_id: str, class_id: str, team_id: str) -> LearningClass:
        with self._pool.connection() as conn:
            with conn.transaction():
                self._lock_class(conn, user_id=user_id, class_id=class_id, team_id=team_id)
                row = conn.execute(
                    """
                    UPDATE learning_classes
                    SET status = 'ended', ended_at = now(), updated_at = now()
                    WHERE user_id = %s AND class_id = %s
                    RETURNING class_id, user_id, team_id, learning_goal, status, started_at, ended_at
                    """,
                    (user_id, class_id),
                ).fetchone()
        self._invalidate_context(user_id=user_id, class_id=class_id)
        return self._class_from_row(row)

    def close(self) -> None:
        return None

    def _lock_class(self, conn, *, user_id: str, class_id: str, team_id: str) -> None:
        conn.execute(
            """
            INSERT INTO user_accounts (user_id)
            VALUES (%s)
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id,),
        )
        conn.execute(
            """
            INSERT INTO learning_classes (class_id, user_id, team_id, learning_goal)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (class_id) DO NOTHING
            """,
            (class_id, user_id, team_id, team_id),
        )
        conn.execute(
            """
            SELECT class_id FROM learning_classes
            WHERE user_id = %s AND class_id = %s
            FOR UPDATE
            """,
            (user_id, class_id),
        ).fetchone()

    def _invalidate_context(self, *, user_id: str, class_id: str) -> None:
        if self.cache is not None:
            self.cache.delete(self.cache.learning_context_key(user_id=user_id, class_id=class_id))

    @staticmethod
    def _class_from_row(row: Dict[str, Any]) -> LearningClass:
        return LearningClass(
            class_id=str(row["class_id"]),
            user_id=str(row["user_id"]),
            team_id=str(row["team_id"]),
            learning_goal=str(row["learning_goal"]),
            status=str(row["status"]),
            started_at=str(row["started_at"]),
            ended_at=str(row["ended_at"]) if row.get("ended_at") is not None else None,
        )

    @staticmethod
    def _record_from_row(row: Dict[str, Any]) -> LearningProgressRecord:
        return LearningProgressRecord(
            record_id=str(row["record_id"]),
            class_id=str(row["class_id"]),
            user_id=str(row["user_id"]),
            team_id=str(row["team_id"]),
            source_agent=str(row["source_agent"]),
            record_type=str(row["record_type"]),
            content=str(row["content"]),
            metadata=_metadata(row.get("metadata")),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _summary_from_row(row: Dict[str, Any]) -> LearningSummary:
        return LearningSummary(
            summary_id=str(row["summary_id"]),
            class_id=str(row["class_id"]),
            user_id=str(row["user_id"]),
            team_id=str(row["team_id"]),
            summary=str(row["summary"]),
            generated_by=str(row["generated_by"]),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _bundle_from_dict(payload: Dict[str, Any]) -> LearningContextBundle:
        learning_class = LearningClass(**payload["learning_class"])
        records = [LearningProgressRecord(**item) for item in payload.get("recent_records", [])]
        summaries = [LearningSummary(**item) for item in payload.get("summaries", [])]
        return LearningContextBundle(learning_class=learning_class, recent_records=records, summaries=summaries)
