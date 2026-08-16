"""Profile and user class record service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ProfileService:
    def __init__(self, *, repository):
        if repository is None:
            raise RuntimeError("ProfileService requires a persistent repository")
        self.repository = repository

    def upsert_profile(self, *, user_id: str, profile: Dict[str, Any], display_name: Optional[str] = None) -> Dict[str, Any]:
        return self.repository.upsert_profile(user_id=user_id, profile=profile, display_name=display_name)

    def get_profile(self, *, user_id: str) -> Dict[str, Any]:
        return self.repository.get_profile(user_id=user_id)

    def create_class(self, *, user_id: str, team_id: str, learning_goal: str, class_id: Optional[str] = None) -> Dict[str, Any]:
        return self.repository.create_class(user_id=user_id, team_id=team_id, learning_goal=learning_goal, class_id=class_id)

    def get_class(self, *, user_id: str, class_id: str) -> Dict[str, Any]:
        item = self.repository.get_class(user_id=user_id, class_id=class_id)
        if item is None:
            raise ValueError("class not found")
        return item

    def list_classes(self, *, user_id: str, status: str = "active") -> List[Dict[str, Any]]:
        return self.repository.list_classes(user_id=user_id, status=status)

    def update_class(self, *, user_id: str, class_id: str, learning_goal: Optional[str] = None, status: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.repository.update_class(user_id=user_id, class_id=class_id, learning_goal=learning_goal, status=status, metadata=metadata)

    def archive_class(self, *, user_id: str, class_id: str) -> Dict[str, Any]:
        return self.repository.archive_class(user_id=user_id, class_id=class_id)
