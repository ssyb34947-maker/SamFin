"""Exercise API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateExerciseAttemptRequest(BaseModel):
    user_id: str
    class_id: str
    team_id: str
    source_agent: Optional[str] = None
    items: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateExerciseAttemptRequest(BaseModel):
    status: Optional[str] = None
    score: Optional[float] = None
    max_score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
