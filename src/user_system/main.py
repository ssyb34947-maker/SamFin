"""
Executable entrypoint for the user system service.
"""

from __future__ import annotations

import os

def run() -> None:
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise RuntimeError("User system service requires the 'uvicorn' package to run.") from exc

    host = os.getenv("USER_SYSTEM_HOST", "")
    port_value = os.getenv("USER_SYSTEM_PORT", "")
    if not host or not port_value:
        raise RuntimeError("USER_SYSTEM_HOST and USER_SYSTEM_PORT are required to start the user system service")
    uvicorn.run("src.user_system.app:app", host=host, port=int(port_value), factory=False)


if __name__ == "__main__":
    run()
