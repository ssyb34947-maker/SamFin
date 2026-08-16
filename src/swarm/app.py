"""Swarm FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import get_config
from src.swarm.runtime import EducationCompanyRuntime


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.swarm_runtime = EducationCompanyRuntime.from_config(get_config())
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="SamLang Swarm", version="0.2.0", lifespan=lifespan)

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "swarm", "version": "0.2.0"}

    @app.post("/chat")
    async def chat(payload: dict):
        runtime = app.state.swarm_runtime
        result = await runtime.chat(
            str(payload.get("message", "")),
            session_id=payload.get("session_id"),
        )
        return {
            "final_output": result.final_output,
            "session_id": result.session_id,
            "active_team": result.active_team,
            "trace": [event.to_dict() for event in result.trace],
        }

    @app.get("/graph")
    async def graph():
        return app.state.swarm_runtime.graph_summary()

    @app.get("/sessions/{session_id}/progress")
    async def progress(session_id: str):
        return app.state.swarm_runtime.progress_snapshot(session_id=session_id)

    @app.get("/sessions/{session_id}/calls")
    async def calls(session_id: str):
        return {"calls": app.state.swarm_runtime.communication_log(session_id=session_id)}

    return app


app = create_app()
