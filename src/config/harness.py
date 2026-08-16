"""Harness configuration."""

from dataclasses import dataclass


@dataclass
class HarnessConfig:
    """Configuration for a single agent harness."""

    memory_type: str = "buffer"
    max_history: int = 10
    max_agent_turns: int = 5


AgentConfig = HarnessConfig

__all__ = ["HarnessConfig", "AgentConfig"]
