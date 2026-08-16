"""
Schemas for the user system learning context boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class LearningClass:
    class_id: str
    user_id: str
    team_id: str
    learning_goal: str
    status: str = "active"
    started_at: str = field(default_factory=utc_now_iso)
    ended_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_id": self.class_id,
            "user_id": self.user_id,
            "team_id": self.team_id,
            "learning_goal": self.learning_goal,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


@dataclass
class LearningProgressRecord:
    record_id: str
    class_id: str
    user_id: str
    team_id: str
    source_agent: str
    record_type: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "class_id": self.class_id,
            "user_id": self.user_id,
            "team_id": self.team_id,
            "source_agent": self.source_agent,
            "record_type": self.record_type,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class LearningSummary:
    summary_id: str
    class_id: str
    user_id: str
    team_id: str
    summary: str
    generated_by: str
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_id": self.summary_id,
            "class_id": self.class_id,
            "user_id": self.user_id,
            "team_id": self.team_id,
            "summary": self.summary,
            "generated_by": self.generated_by,
            "created_at": self.created_at,
        }


@dataclass
class LearningContextBundle:
    learning_class: LearningClass
    recent_records: List[LearningProgressRecord] = field(default_factory=list)
    summaries: List[LearningSummary] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "learning_class": self.learning_class.to_dict(),
            "recent_records": [record.to_dict() for record in self.recent_records],
            "summaries": [summary.to_dict() for summary in self.summaries],
        }
