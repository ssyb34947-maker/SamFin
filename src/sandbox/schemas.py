"""Request and response schemas for the sandbox service."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SandboxLanguage(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    DUCKDB_SQL = "duckdb_sql"


class Artifact(BaseModel):
    artifact_id: str
    filename: str
    size_bytes: int
    download_path: str


class SandboxRunRequest(BaseModel):
    language: SandboxLanguage
    code: str = Field(min_length=1)
    files: Dict[str, str] = Field(default_factory=dict)
    timeout_seconds: Optional[int] = None


class SandboxRunResponse(BaseModel):
    job_id: str
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    execution_time_ms: float = 0.0
    result: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[Artifact] = Field(default_factory=list)
    truncated: bool = False
    error: str = ""


class SandboxJobStatus(BaseModel):
    job_id: str
    status: str
    created_at: float
    execution_time_ms: float = 0.0
