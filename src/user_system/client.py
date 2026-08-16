"""Client boundary for the user system service."""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from .modules.learning.service import LearningContextService


class UserSystemClientConfigError(ValueError):
    """Raised when user system client configuration is incomplete."""


class UserSystemClient:
    def __init__(
        self,
        *,
        mode: str = "remote",
        base_url: str = "",
        timeout: float = 10.0,
        local_service: Optional[LearningContextService] = None,
    ):
        self.mode = mode
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.local_service = local_service
        if self.mode == "remote" and not self.base_url:
            raise UserSystemClientConfigError("user_system.base_url is required when user_system.mode is remote")
        if self.mode == "local" and self.local_service is None:
            raise UserSystemClientConfigError("local user system client requires an explicit local_service")

    def query_learning_progress(
        self,
        *,
        user_id: str,
        class_id: str,
        team_id: str,
        recent_limit: int = 8,
    ) -> Dict[str, Any]:
        if self.mode == "remote":
            response = requests.get(
                f"{self.base_url}/learning-context/{user_id}/{class_id}",
                params={"team_id": team_id, "recent_limit": recent_limit},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        return self.local_service.query_progress(user_id=user_id, class_id=class_id, team_id=team_id, recent_limit=recent_limit)

    def append_learning_progress(
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
        payload = {
            "user_id": user_id,
            "class_id": class_id,
            "team_id": team_id,
            "source_agent": source_agent,
            "record_type": record_type,
            "content": content,
            "metadata": metadata or {},
        }
        if self.mode == "remote":
            response = requests.post(f"{self.base_url}/learning-context/progress", json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        return self.local_service.append_progress(**payload)

    def flush_learning_context(self, *, user_id: str, class_id: str) -> Dict[str, Any]:
        if self.mode == "remote":
            response = requests.post(f"{self.base_url}/learning-context/{user_id}/{class_id}/flush", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        return {"flushed_records": self.local_service.flush_context(user_id=user_id, class_id=class_id)}
