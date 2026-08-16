"""Exercise record service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ExerciseService:
    def __init__(self, *, repository):
        if repository is None:
            raise RuntimeError("ExerciseService requires a persistent repository")
        self.repository = repository

    def create_exercise_attempt(self, *, user_id: str, class_id: str, team_id: str, source_agent: Optional[str], items: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
        return self.repository.create_exercise_attempt(user_id=user_id, class_id=class_id, team_id=team_id, source_agent=source_agent, items=items, metadata=metadata)

    def get_exercise_attempt(self, *, attempt_id: str) -> Dict[str, Any]:
        item = self.repository.get_exercise_attempt(attempt_id=attempt_id)
        if item is None:
            raise ValueError("attempt not found")
        return item

    def list_exercise_attempts(self, *, user_id: str, class_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.repository.list_exercise_attempts(user_id=user_id, class_id=class_id)

    def update_attempt(self, *, attempt_id: str, status: Optional[str] = None, score: Optional[float] = None, max_score: Optional[float] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.repository.update_attempt(attempt_id=attempt_id, status=status, score=score, max_score=max_score, metadata=metadata)

    def archive_attempt(self, *, attempt_id: str) -> Dict[str, Any]:
        return self.repository.archive_attempt(attempt_id=attempt_id)
