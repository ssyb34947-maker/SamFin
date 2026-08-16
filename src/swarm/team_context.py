"""
Team progress helpers backed by Agency Swarm shared context.

Agency Swarm exposes shared state through ``MasterContext.user_context``. This
module defines the project schema stored in that dict; it intentionally does not
own a separate storage layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from agency_swarm import MasterContext


TEAM_PROGRESS_KEY = "team_progress"
LEARNING_CONTEXT_WINDOW_KEY = "learning_context_window"
ASSISTANT_TASK_SCRATCH_KEY = "assistant_task_scratch"
SharedUserContext = Dict[str, Any] | MasterContext


def _now() -> str:
    return datetime.now().isoformat()


def resolve_user_context(user_context: SharedUserContext) -> Dict[str, Any]:
    if isinstance(user_context, MasterContext):
        return user_context.user_context
    return user_context


def ensure_team_progress(user_context: SharedUserContext, team_id: str, session_id: str) -> Dict[str, Any]:
    user_context = resolve_user_context(user_context)
    progress_by_team = user_context.setdefault(TEAM_PROGRESS_KEY, {})
    team_progress = progress_by_team.setdefault(team_id, {})
    return team_progress.setdefault(
        session_id,
        {
            "team_id": team_id,
            "session_id": session_id,
            "learning_progress": {},
            "work_log": [],
        },
    )


def update_learning_progress(
    user_context: SharedUserContext,
    team_id: str,
    session_id: str,
    source_agent: str,
    updates: Dict[str, Any],
    note: str = "",
) -> Dict[str, Any]:
    progress = ensure_team_progress(user_context=user_context, team_id=team_id, session_id=session_id)
    learning_progress = progress.setdefault("learning_progress", {})
    for key, value in updates.items():
        if value is None or value == "":
            continue
        learning_progress[str(key)] = {
            "key": str(key),
            "value": value,
            "source_agent": source_agent,
            "updated_at": _now(),
            "note": note,
        }
    return progress


def append_work_log(
    user_context: SharedUserContext,
    team_id: str,
    session_id: str,
    source_agent: str,
    content: str,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    progress = ensure_team_progress(user_context=user_context, team_id=team_id, session_id=session_id)
    progress.setdefault("work_log", []).append(
        {
            "source_agent": source_agent,
            "content": content,
            "metadata": metadata or {},
            "created_at": _now(),
        }
    )
    return progress


def set_learning_context_window(
    user_context: SharedUserContext,
    team_id: str,
    session_id: str,
    window: Dict[str, Any],
) -> Dict[str, Any]:
    user_context = resolve_user_context(user_context)
    windows_by_team = user_context.setdefault(LEARNING_CONTEXT_WINDOW_KEY, {})
    team_windows = windows_by_team.setdefault(team_id, {})
    team_windows[session_id] = window
    return window


def get_learning_context_window(user_context: SharedUserContext, team_id: str, session_id: str) -> Dict[str, Any]:
    user_context = resolve_user_context(user_context)
    return user_context.get(LEARNING_CONTEXT_WINDOW_KEY, {}).get(team_id, {}).get(session_id, {})


def ensure_assistant_task_scratch(
    user_context: SharedUserContext,
    team_id: str,
    session_id: str,
    parent_task_id: str,
    parent_agent: str = "",
    task: str = "",
) -> Dict[str, Any]:
    user_context = resolve_user_context(user_context)
    scratch_by_team = user_context.setdefault(ASSISTANT_TASK_SCRATCH_KEY, {})
    team_scratch = scratch_by_team.setdefault(team_id, {})
    session_scratch = team_scratch.setdefault(session_id, {})
    return session_scratch.setdefault(
        parent_task_id,
        {
            "team_id": team_id,
            "session_id": session_id,
            "parent_task_id": parent_task_id,
            "parent_agent": parent_agent,
            "task": task,
            "persistence": "ephemeral",
            "created_at": _now(),
            "assistant_outputs": [],
        },
    )


def append_assistant_task_output(
    user_context: SharedUserContext,
    team_id: str,
    session_id: str,
    parent_task_id: str,
    assistant_agent: str,
    content: str,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    scratch = ensure_assistant_task_scratch(
        user_context=user_context,
        team_id=team_id,
        session_id=session_id,
        parent_task_id=parent_task_id,
    )
    scratch.setdefault("assistant_outputs", []).append(
        {
            "assistant_agent": assistant_agent,
            "content": content,
            "metadata": metadata or {},
            "created_at": _now(),
        }
    )
    scratch["updated_at"] = _now()
    return scratch


def get_assistant_task_scratch(
    user_context: SharedUserContext,
    team_id: str,
    session_id: str,
    parent_task_id: str,
) -> Dict[str, Any]:
    user_context = resolve_user_context(user_context)
    return (
        user_context.get(ASSISTANT_TASK_SCRATCH_KEY, {})
        .get(team_id, {})
        .get(session_id, {})
        .get(parent_task_id, {})
    )


def snapshot_team_progress(user_context: SharedUserContext, team_id: str, session_id: str) -> Dict[str, Any]:
    return ensure_team_progress(user_context=user_context, team_id=team_id, session_id=session_id)
