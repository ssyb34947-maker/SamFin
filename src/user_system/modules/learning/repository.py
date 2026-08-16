"""Repository protocol for user learning context."""

from __future__ import annotations

from typing import Optional, Protocol

from .schemas import LearningClass, LearningContextBundle, LearningProgressRecord, LearningSummary


class UserLearningRepository(Protocol):
    """Persistent learning repository contract."""

    def get_or_create_class(self, *, user_id: str, class_id: str, team_id: str, learning_goal: str) -> LearningClass:
        ...

    def get_context(self, *, user_id: str, class_id: str, team_id: str, recent_limit: int = 8) -> LearningContextBundle:
        ...

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
        ...

    def save_summary(
        self,
        *,
        user_id: str,
        class_id: str,
        team_id: str,
        summary: str,
        generated_by: str,
    ) -> LearningSummary:
        ...

    def end_class(self, *, user_id: str, class_id: str, team_id: str) -> LearningClass:
        ...
