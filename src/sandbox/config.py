"""Configuration for the local Docker sandbox service."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml


@dataclass(frozen=True)
class SandboxServerConfig:
    host: str = ""
    port: int = 0


@dataclass(frozen=True)
class SandboxDockerConfig:
    runtime_image: str = ""
    network_disabled: bool = True
    memory_limit: str = "512m"
    nano_cpus: int = 1_000_000_000
    pids_limit: int = 128
    read_only_root: bool = True
    user: str = "1000:1000"


@dataclass(frozen=True)
class SandboxLimitsConfig:
    timeout_seconds: int = 10
    max_code_bytes: int = 200_000
    max_output_bytes: int = 200_000
    max_file_bytes: int = 5_000_000
    max_artifact_bytes: int = 10_000_000
    max_artifacts: int = 20
    sql_default_limit: int = 500
    sql_max_limit: int = 1000


@dataclass(frozen=True)
class SandboxPoolConfig:
    size: int = 2
    acquire_timeout_seconds: int = 10


@dataclass(frozen=True)
class SandboxSecurityConfig:
    python_allowed_imports: List[str] = field(default_factory=lambda: [
        "csv", "datetime", "decimal", "duckdb", "fractions", "json", "math", "matplotlib",
        "numpy", "openpyxl", "pandas", "pyarrow", "re", "scipy", "statistics",
    ])
    javascript_allowed_imports: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class SandboxSettings:
    server: SandboxServerConfig = field(default_factory=SandboxServerConfig)
    docker: SandboxDockerConfig = field(default_factory=SandboxDockerConfig)
    limits: SandboxLimitsConfig = field(default_factory=SandboxLimitsConfig)
    pool: SandboxPoolConfig = field(default_factory=SandboxPoolConfig)
    security: SandboxSecurityConfig = field(default_factory=SandboxSecurityConfig)
    workspace_root: Path = Path("/tmp/samlang-sandbox/workspaces")
    artifact_root: Path = Path("/tmp/samlang-sandbox/artifacts")

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SandboxSettings":
        config_file = Path(path)
        if not config_file.exists():
            raise FileNotFoundError(f"sandbox config file not found: {config_file}")
        data = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        sandbox = data.get("sandbox", data)
        return cls(
            server=SandboxServerConfig(**sandbox.get("server", {})),
            docker=SandboxDockerConfig(**sandbox.get("docker", {})),
            limits=SandboxLimitsConfig(**sandbox.get("limits", {})),
            pool=SandboxPoolConfig(**sandbox.get("pool", {})),
            security=SandboxSecurityConfig(**sandbox.get("security", {})),
            workspace_root=Path(sandbox.get("workspace_root", "/tmp/samlang-sandbox/workspaces")),
            artifact_root=Path(sandbox.get("artifact_root", "/tmp/samlang-sandbox/artifacts")),
        )


_settings: SandboxSettings | None = None


def _settings_path(path: str | None = None) -> str:
    return path or os.getenv("SANDBOX_CONFIG_PATH", "config/sandbox/config.yaml")


def get_settings(path: str | None = None) -> SandboxSettings:
    global _settings
    if _settings is None or path is not None:
        _settings = SandboxSettings.from_yaml(_settings_path(path))
    return _settings


def reload_settings(path: str | None = None) -> SandboxSettings:
    global _settings
    _settings = SandboxSettings.from_yaml(_settings_path(path))
    return _settings
