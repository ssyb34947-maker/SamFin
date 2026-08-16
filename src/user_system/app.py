"""User system FastAPI application assembly."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI

from src.config import get_config

from .factory import UserSystemServices, build_user_system_services
from .modules.auth.router import router as auth_router
from .modules.commerce.router import router as commerce_router
from .modules.exercise.router import router as exercise_router
from .modules.learning.router import router as learning_router
from .modules.profile.router import router as profile_router


def build_services() -> UserSystemServices:
    config = get_config()
    return build_user_system_services(config.user_system)


def verify_schema_ready(services: UserSystemServices) -> None:
    services.verify_schema_ready()


@asynccontextmanager
async def lifespan(app: FastAPI):
    services = build_services()
    verify_schema_ready(services)
    app.state.user_system_services = services
    app.state.auth_service = services.auth_service
    app.state.profile_service = services.profile_service
    app.state.learning_context_service = services.learning_context_service
    app.state.chat_service = services.chat_service
    app.state.exercise_service = services.exercise_service
    app.state.commerce_service = services.commerce_service
    try:
        yield
    finally:
        services.close()


def create_app() -> FastAPI:
    app = FastAPI(title="SamFin User System", version="0.1.0", lifespan=lifespan)
    app.include_router(auth_router)
    app.include_router(profile_router)
    app.include_router(commerce_router)
    app.include_router(exercise_router)
    app.include_router(learning_router)

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
