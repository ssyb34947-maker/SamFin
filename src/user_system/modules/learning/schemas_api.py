"""Learning API schemas."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ProgressRecordRequest(BaseModel):
    user_id: str
    class_id: str
    team_id: str
    source_agent: str
    record_type: str = "note"
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateClassRequest(BaseModel):
    user_id: str
    team_id: str
    learning_goal: str
    class_id: Optional[str] = None
