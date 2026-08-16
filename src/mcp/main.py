"""Run the MCP tool service as an independent process."""

from __future__ import annotations

import os
from dataclasses import dataclass

import uvicorn

from src.mcp.app import create_asgi_app
from src.config import get_config


@dataclass(frozen=True)
class MCPRunSettings:
    host: str
    port: int
    transport: str
    path: str
    health_path: str


def load_run_settings() -> MCPRunSettings:
    config = get_config().tool.mcp
    host = os.getenv("MCP_SERVICE_HOST", getattr(config, "host", ""))
    port_value = os.getenv("MCP_SERVICE_PORT", str(getattr(config, "port", "") or ""))
    transport = os.getenv("MCP_SERVICE_TRANSPORT", getattr(config, "transport", "sse") or "sse")
    path = os.getenv("MCP_SERVICE_PATH", "/sse")
    health_path = os.getenv("MCP_SERVICE_HEALTH_PATH", getattr(config, "health_path", "/health") or "/health")

    if not host or not port_value:
        raise RuntimeError("MCP_SERVICE_HOST and MCP_SERVICE_PORT or tool.mcp.host and tool.mcp.port are required")
    return MCPRunSettings(host=host, port=int(port_value), transport=transport, path=path, health_path=health_path)


def run() -> None:
    settings = load_run_settings()
    app = create_asgi_app(path=settings.path, health_path=settings.health_path, transport=settings.transport)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
