"""
Learning progress MCP tools for teaching teams.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from fastmcp import FastMCP

from src.user_system import UserSystemClient

learning_progress_mcp = FastMCP(name="learning_progress")


def _user_system_base_url(explicit_base_url: Optional[str]) -> str:
    if explicit_base_url:
        return explicit_base_url
    env_base_url = os.getenv("USER_SYSTEM_BASE_URL", "")
    if env_base_url:
        return env_base_url
    try:
        from src.config import get_config

        return get_config().user_system.base_url
    except Exception:
        return ""


def query_learning_progress(
    user_id: str,
    class_id: str,
    team_id: str,
    recent_limit: int = 8,
    user_system_base_url: Optional[str] = None,
    user_system_mode: str = "remote",
) -> str:
    client = UserSystemClient(
        mode=user_system_mode,
        base_url=_user_system_base_url(user_system_base_url),
    )
    payload = client.query_learning_progress(
        user_id=user_id,
        class_id=class_id,
        team_id=team_id,
        recent_limit=recent_limit,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def append_learning_progress_record(
    user_id: str,
    class_id: str,
    team_id: str,
    source_agent: str,
    record_type: str,
    content: str,
    metadata_json: str = "{}",
    user_system_base_url: Optional[str] = None,
    user_system_mode: str = "remote",
) -> str:
    try:
        metadata = json.loads(metadata_json or "{}")
        if not isinstance(metadata, dict):
            metadata = {}
    except json.JSONDecodeError:
        metadata = {}
    client = UserSystemClient(
        mode=user_system_mode,
        base_url=_user_system_base_url(user_system_base_url),
    )
    payload = client.append_learning_progress(
        user_id=user_id,
        class_id=class_id,
        team_id=team_id,
        source_agent=source_agent,
        record_type=record_type,
        content=content,
        metadata=metadata,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)
