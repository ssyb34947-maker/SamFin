"""Run the swarm service."""

from __future__ import annotations

import os

import uvicorn


def run() -> None:
    host = os.getenv("SWARM_SERVICE_HOST", "0.0.0.0")
    port = int(os.getenv("SWARM_SERVICE_PORT", "8004"))
    uvicorn.run("src.swarm.app:app", host=host, port=port)


if __name__ == "__main__":
    run()
