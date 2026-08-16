"""Run the sandbox service."""

from __future__ import annotations

import os

import uvicorn

from .app import create_app
from .config import get_settings


def run() -> None:
    settings = get_settings()
    host = os.getenv("SANDBOX_SERVICE_HOST", settings.server.host)
    port_value = os.getenv("SANDBOX_SERVICE_PORT", str(settings.server.port or ""))
    if not host or not port_value:
        raise RuntimeError("SANDBOX_SERVICE_HOST and SANDBOX_SERVICE_PORT or sandbox.server.host and port are required")
    uvicorn.run(create_app(), host=host, port=int(port_value))


if __name__ == "__main__":
    run()
