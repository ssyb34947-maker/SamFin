"""Swarm runtime configuration."""

from dataclasses import dataclass
from typing import List


@dataclass
class SwarmConfig:
    """Configuration for the Agency Swarm education runtime."""

    enabled: bool = True
    runtime: str = "agents"
    pilot_team: str = ""
    model_provider: str = "existing_llm_config"
    trace_enabled: bool = True
    teams_dir: str = "team"
    enabled_team_ids: List[str] = None

    def __post_init__(self):
        if self.enabled_team_ids is None:
            self.enabled_team_ids = ["cpa"]


EducationCompanyConfig = SwarmConfig

__all__ = ["SwarmConfig", "EducationCompanyConfig"]
