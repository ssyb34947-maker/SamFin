"""FastAPI assembly for the sandbox service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .config import get_settings
from .runner import SandboxRunner
from .schemas import SandboxJobStatus, SandboxRunRequest, SandboxRunResponse


def build_runner() -> SandboxRunner:
    return SandboxRunner(get_settings())


@asynccontextmanager
async def lifespan(app: FastAPI):
    runner = build_runner()
    runner.start()
    app.state.sandbox_runner = runner
    try:
        yield
    finally:
        runner.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="SamFin Sandbox Service", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> Dict[str, object]:
        runner = getattr(app.state, "sandbox_runner", None)
        return {"status": "ok", "pool_size": runner.pool.size if runner else 0}

    @app.post("/sandbox/run", response_model=SandboxRunResponse)
    def run_sandbox(payload: SandboxRunRequest) -> SandboxRunResponse:
        return app.state.sandbox_runner.run(payload)

    @app.get("/sandbox/jobs/{job_id}", response_model=SandboxJobStatus)
    def get_job(job_id: str) -> SandboxJobStatus:
        record = app.state.sandbox_runner.jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="job not found")
        return SandboxJobStatus(**record.__dict__)

    @app.get("/sandbox/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str):
        try:
            path = app.state.sandbox_runner.workspace.artifact_path(artifact_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="artifact not found")
        return FileResponse(path, filename=path.name)

    return app


app = create_app()
