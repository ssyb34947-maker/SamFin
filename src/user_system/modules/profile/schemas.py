"""Profile API schemas."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    profile: Dict[str, Any] = Field(default_factory=dict)


class UpdateClassRequest(BaseModel):
    learning_goal: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
