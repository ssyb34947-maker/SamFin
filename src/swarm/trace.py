"""
Trace recording for education company runs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .schemas import CompanyTraceEvent


class TraceRecorder:
    """Collects structured trace events for one run."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.events: List[CompanyTraceEvent] = []

    def add(
        self,
        event_type: str,
        *,
        agent_name: Optional[str] = None,
        target_name: Optional[str] = None,
        tool_name: Optional[str] = None,
        content: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled:
            return
        self.events.append(
            CompanyTraceEvent(
                event_type=event_type,
                agent_name=agent_name,
                target_name=target_name,
                tool_name=tool_name,
                content=content,
                metadata=metadata or {},
            )
        )
