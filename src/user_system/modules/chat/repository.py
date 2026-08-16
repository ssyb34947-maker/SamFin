"""PostgreSQL repository for learning chats."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from src.user_system.common.postgres import PostgreSQLStore


class ChatRepository(Protocol):
    def create_chat(self, *, user_id: str, class_id: str, team_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        ...

    def get_chat(self, *, chat_id: str) -> Optional[Dict[str, Any]]:
        ...

    def list_chats(self, *, user_id: str, class_id: str, include_history: bool = True) -> List[Dict[str, Any]]:
        ...

    def update_chat(self, *, chat_id: str, title: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        ...

    def mark_chat_history(self, *, chat_id: str) -> Dict[str, Any]:
        ...

    def append_message(self, *, chat_id: str, user_id: str, class_id: str, role: str, content: str, source_agent: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...

    def list_messages(self, *, chat_id: str) -> List[Dict[str, Any]]:
        ...


class PostgreSQLChatRepository:
    def __init__(self, store: PostgreSQLStore):
        self.store = store

    def create_chat(self, *, user_id: str, class_id: str, team_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                INSERT INTO learning_chats (chat_id, user_id, class_id, team_id, title)
                VALUES ('chat_' || substr(md5(random()::text || clock_timestamp()::text), 1, 12), %s, %s, %s, %s)
                RETURNING chat_id, user_id, class_id, team_id, title, status, is_history, started_at, ended_at, summary_id, branch_from_chat_id, metadata, created_at, updated_at
                """,
                (user_id, class_id, team_id, title),
            ).fetchone()
        self.store.delete_cached_pattern("chats", user_id, class_id, "*")
        return dict(row)

    def get_chat(self, *, chat_id: str) -> Optional[Dict[str, Any]]:
        cached = self.store.get_cached_json("chat", chat_id)
        if cached is not None:
            return cached
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                SELECT chat_id, user_id, class_id, team_id, title, status, is_history, started_at, ended_at, summary_id, branch_from_chat_id, metadata, created_at, updated_at
                FROM learning_chats
                WHERE chat_id = %s AND status != 'deleted'
                """,
                (chat_id,),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        self.store.set_cached_json(payload, "chat", chat_id)
        return payload

    def list_chats(self, *, user_id: str, class_id: str, include_history: bool = True) -> List[Dict[str, Any]]:
        cached = self.store.get_cached_json("chats", user_id, class_id, include_history)
        if cached is not None:
            return list(cached["items"])
        history_filter = "" if include_history else "AND is_history = false"
        with self.store.pool.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT chat_id, user_id, class_id, team_id, title, status, is_history, started_at, ended_at, summary_id, branch_from_chat_id, metadata, created_at, updated_at
                FROM learning_chats
                WHERE user_id = %s AND class_id = %s AND status != 'deleted' {history_filter}
                ORDER BY updated_at DESC
                """,
                (user_id, class_id),
            ).fetchall()
        items = [dict(row) for row in rows]
        self.store.set_cached_json({"items": items}, "chats", user_id, class_id, include_history)
        return items

    def update_chat(self, *, chat_id: str, title: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                UPDATE learning_chats
                SET title = COALESCE(%s, title),
                    status = COALESCE(%s, status),
                    ended_at = CASE WHEN %s IN ('ended', 'archived', 'deleted') THEN now() ELSE ended_at END,
                    is_history = CASE WHEN %s IN ('ended', 'archived') THEN true ELSE is_history END,
                    updated_at = now()
                WHERE chat_id = %s
                RETURNING chat_id, user_id, class_id, team_id, title, status, is_history, started_at, ended_at, summary_id, branch_from_chat_id, metadata, created_at, updated_at
                """,
                (title, status, status, status, chat_id),
            ).fetchone()
        if row is None:
            raise ValueError("chat not found")
        self._invalidate_chat(dict(row))
        return dict(row)

    def mark_chat_history(self, *, chat_id: str) -> Dict[str, Any]:
        return self.update_chat(chat_id=chat_id, status="ended")

    def append_message(self, *, chat_id: str, user_id: str, class_id: str, role: str, content: str, source_agent: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        chat = self.get_chat(chat_id=chat_id)
        if chat is None:
            raise ValueError("chat not found")
        if chat.get("is_history"):
            raise ValueError("history chat is read-only")
        with self.store.pool.connection() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    INSERT INTO learning_chat_messages (message_id, chat_id, user_id, class_id, role, content, source_agent, metadata)
                    VALUES ('msg_' || substr(md5(random()::text || clock_timestamp()::text), 1, 12), %s, %s, %s, %s, %s, %s, %s)
                    RETURNING message_id, chat_id, user_id, class_id, role, content, source_agent, prompt_tokens, completion_tokens, total_tokens, metadata, created_at
                    """,
                    (chat_id, user_id, class_id, role, content, source_agent, self.store.jsonb(metadata or {})),
                ).fetchone()
                conn.execute("UPDATE learning_chats SET updated_at = now() WHERE chat_id = %s", (chat_id,))
        self.store.delete_cached("messages", chat_id)
        self._invalidate_chat(chat)
        return dict(row)

    def list_messages(self, *, chat_id: str) -> List[Dict[str, Any]]:
        cached = self.store.get_cached_json("messages", chat_id)
        if cached is not None:
            return list(cached["items"])
        with self.store.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT message_id, chat_id, user_id, class_id, role, content, source_agent, prompt_tokens, completion_tokens, total_tokens, metadata, created_at
                FROM learning_chat_messages
                WHERE chat_id = %s
                ORDER BY created_at ASC
                """,
                (chat_id,),
            ).fetchall()
        items = [dict(row) for row in rows]
        self.store.set_cached_json({"items": items}, "messages", chat_id)
        return items

    def _invalidate_chat(self, chat: Dict[str, Any]) -> None:
        self.store.delete_cached("chat", chat["chat_id"])
        self.store.delete_cached_pattern("chats", chat["user_id"], chat["class_id"], "*")
