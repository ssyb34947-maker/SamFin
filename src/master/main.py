"""Run the frontend-master service."""

from __future__ import annotations

import os

import uvicorn


def run() -> None:
    host = os.getenv("MASTER_SERVICE_HOST", "0.0.0.0")
    port = int(os.getenv("MASTER_SERVICE_PORT", "8000"))
    uvicorn.run("src.master.app:app", host=host, port=port)


if __name__ == "__main__":
    run()
