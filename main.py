"""Compatibility entrypoint for the frontend-master service."""

from src.master.app import app, create_app

__all__ = ["app", "create_app"]


if __name__ == "__main__":
    from src.master.main import run

    run()
