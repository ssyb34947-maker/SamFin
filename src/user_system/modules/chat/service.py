"""Learning chat history service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ChatService:
    def __init__(self, *, repository):
        if repository is None:
            raise RuntimeError("ChatService requires a persistent repository")
        self.repository = repository

    def create_chat(self, *, user_id: str, class_id: str, team_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        return self.repository.create_chat(user_id=user_id, class_id=class_id, team_id=team_id, title=title)

    def get_chat(self, *, chat_id: str) -> Dict[str, Any]:
        item = self.repository.get_chat(chat_id=chat_id)
        if item is None:
            raise ValueError("chat not found")
        return item

    def list_chats(self, *, user_id: str, class_id: str, include_history: bool = True) -> List[Dict[str, Any]]:
        return self.repository.list_chats(user_id=user_id, class_id=class_id, include_history=include_history)

    def update_chat(self, *, chat_id: str, title: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        return self.repository.update_chat(chat_id=chat_id, title=title, status=status)

    def append_message(self, *, chat_id: str, user_id: str, class_id: str, role: str, content: str, source_agent: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.repository.append_message(chat_id=chat_id, user_id=user_id, class_id=class_id, role=role, content=content, source_agent=source_agent, metadata=metadata)

    def list_messages(self, *, chat_id: str) -> List[Dict[str, Any]]:
        return self.repository.list_messages(chat_id=chat_id)

    def mark_chat_history(self, *, chat_id: str) -> Dict[str, Any]:
        return self.repository.mark_chat_history(chat_id=chat_id)

    def archive_chat(self, *, chat_id: str) -> Dict[str, Any]:
        return self.repository.update_chat(chat_id=chat_id, status="archived")
