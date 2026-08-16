"""Chat API schemas."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CreateChatRequest(BaseModel):
    user_id: str
    class_id: Optional[str] = None
    team_id: str
    title: Optional[str] = None


class UpdateChatRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


class AppendMessageRequest(BaseModel):
    user_id: str
    class_id: str
    role: str
    content: str
    source_agent: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
