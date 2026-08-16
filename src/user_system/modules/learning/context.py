"""
Session-scoped learning context cache for the company runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .repository import UserLearningRepository
from .schemas import LearningContextBundle


@dataclass
class WorkingLearningContext:
    user_id: str
    class_id: str
    team_id: str
    bundle: LearningContextBundle
    pending_records: List[Dict[str, Any]] = field(default_factory=list)
    dirty: bool = False

    def summary_window(self, recent_limit: int = 5) -> Dict[str, Any]:
        records = [record.to_dict() for record in self.bundle.recent_records[-recent_limit:]]
        if self.pending_records:
            records.extend(self.pending_records[-recent_limit:])
            records = records[-recent_limit:]
        return {
            "learning_class": self.bundle.learning_class.to_dict(),
            "recent_records": records,
            "summaries": [summary.to_dict() for summary in self.bundle.summaries[-3:]],
        }


class LearningContextService:
    """
    Company-side working context manager.

    It keeps one learning context in memory during a team session. Repository and
    Redis layers are treated as fallback/persistence boundaries.
    """

    def __init__(self, repository: UserLearningRepository):
        if repository is None:
            raise RuntimeError("LearningContextService requires a persistent repository")
        self.repository = repository
        self._working_contexts: Dict[tuple[str, str], WorkingLearningContext] = {}

    def load_context(
        self,
        *,
        user_id: str,
        class_id: str,
        team_id: str,
        learning_goal: str,
        recent_limit: int = 8,
    ) -> WorkingLearningContext:
        key = (user_id, class_id)
        if key in self._working_contexts:
            return self._working_contexts[key]
        self.repository.get_or_create_class(
            user_id=user_id,
            class_id=class_id,
            team_id=team_id,
            learning_goal=learning_goal,
        )
        bundle = self.repository.get_context(
            user_id=user_id,
            class_id=class_id,
            team_id=team_id,
            recent_limit=recent_limit,
        )
        context = WorkingLearningContext(user_id=user_id, class_id=class_id, team_id=team_id, bundle=bundle)
        self._working_contexts[key] = context
        return context

    def get_loaded_context(self, *, user_id: str, class_id: str) -> Optional[WorkingLearningContext]:
        return self._working_contexts.get((user_id, class_id))

    def append_progress(
        self,
        *,
        user_id: str,
        class_id: str,
        team_id: str,
        source_agent: str,
        record_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = self.load_context(
            user_id=user_id,
            class_id=class_id,
            team_id=team_id,
            learning_goal=team_id,
        )
        pending = {
            "record_id": f"pending_{len(context.pending_records) + 1}",
            "class_id": class_id,
            "user_id": user_id,
            "team_id": team_id,
            "source_agent": source_agent,
            "record_type": record_type,
            "content": content,
            "metadata": metadata or {},
            "created_at": "pending",
        }
        context.pending_records.append(pending)
        context.dirty = True
        return pending

    def query_progress(
        self,
        *,
        user_id: str,
        class_id: str,
        team_id: str,
        recent_limit: int = 8,
        include_pending: bool = True,
    ) -> Dict[str, Any]:
        context = self.load_context(
            user_id=user_id,
            class_id=class_id,
            team_id=team_id,
            learning_goal=team_id,
            recent_limit=recent_limit,
        )
        payload = context.summary_window(recent_limit=recent_limit)
        if include_pending:
            payload["pending_records"] = list(context.pending_records)
        return payload

    def flush_context(self, *, user_id: str, class_id: str) -> int:
        context = self._working_contexts.get((user_id, class_id))
        if context is None or not context.pending_records:
            return 0
        count = 0
        for item in context.pending_records:
            record = self.repository.append_progress_record(
                user_id=user_id,
                class_id=class_id,
                team_id=context.team_id,
                source_agent=str(item.get("source_agent") or "unknown"),
                record_type=str(item.get("record_type") or "note"),
                content=str(item.get("content") or ""),
                metadata=dict(item.get("metadata") or {}),
            )
            context.bundle.recent_records.append(record)
            count += 1
        context.pending_records.clear()
        context.dirty = False
        return count


def get_learning_context_service() -> LearningContextService:
    raise RuntimeError("LearningContextService must be built from user_system configuration")
