"""Compatibility module for the user system service."""

from .app import app, build_services, create_app, lifespan, verify_schema_ready

__all__ = ["app", "build_services", "create_app", "lifespan", "verify_schema_ready"]
