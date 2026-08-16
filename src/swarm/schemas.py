"""
Schemas for the education company runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


TraceEventType = (
    "agent_start",
    "agent_message",
    "handoff",
    "tool_call",
    "tool_result",
    "final_output",
    "error",
)


@dataclass
class CompanyTraceEvent:
    """A structured trace event for one company run."""

    event_type: str
    agent_name: Optional[str] = None
    target_name: Optional[str] = None
    tool_name: Optional[str] = None
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "agent_name": self.agent_name,
            "target_name": self.target_name,
            "tool_name": self.tool_name,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass
class CompanyRunResult:
    """Result returned by the AI education company runtime."""

    final_output: str
    session_id: str
    entry_agent: str = "AcademicDirectorAgent"
    active_team: Optional[str] = None
    trace: List[CompanyTraceEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_output": self.final_output,
            "session_id": self.session_id,
            "entry_agent": self.entry_agent,
            "active_team": self.active_team,
            "trace": [event.to_dict() for event in self.trace],
        }
