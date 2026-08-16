"""Sandbox execution orchestration."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Dict

from .config import SandboxSettings
from .pool import DockerWorkerPool, Worker
from .schemas import SandboxLanguage, SandboxRunRequest, SandboxRunResponse
from .security import SandboxSecurityError, SecurityPolicy, validate_code
from .workspace import JobWorkspace, WorkspaceManager, WorkspaceError


@dataclass
class JobRecord:
    job_id: str
    status: str
    created_at: float
    execution_time_ms: float = 0.0


class SandboxRunner:
    def __init__(self, settings: SandboxSettings):
        self.settings = settings
        self.workspace = WorkspaceManager(
            workspace_root=settings.workspace_root,
            artifact_root=settings.artifact_root,
            max_file_bytes=settings.limits.max_file_bytes,
            max_artifacts=settings.limits.max_artifacts,
            max_artifact_bytes=settings.limits.max_artifact_bytes,
        )
        self.pool = DockerWorkerPool(settings.docker, settings.pool, settings.workspace_root)
        self.jobs: Dict[str, JobRecord] = {}

    def start(self) -> None:
        self.settings.workspace_root.mkdir(parents=True, exist_ok=True)
        self.settings.artifact_root.mkdir(parents=True, exist_ok=True)
        self.pool.start()

    def shutdown(self) -> None:
        self.pool.shutdown()

    def run(self, request: SandboxRunRequest) -> SandboxRunResponse:
        started = time.time()
        workspace = self.workspace.create_job()
        self.jobs[workspace.job_id] = JobRecord(job_id=workspace.job_id, status="running", created_at=started)
        worker = None
        try:
            if len(request.code.encode("utf-8")) > self.settings.limits.max_code_bytes:
                raise SandboxSecurityError("code is too large")
            code = validate_code(request.language, request.code, self._policy())
            self.workspace.write_files(workspace, request.files)
            self._write_program(workspace, request.language, code)
            worker = self.pool.acquire()
            active_timeout = request.timeout_seconds or self.settings.limits.timeout_seconds
            response = self._execute(worker, workspace, request.language, active_timeout, started)
            self.pool.release(worker)
            self.jobs[workspace.job_id].status = response.status
            self.jobs[workspace.job_id].execution_time_ms = response.execution_time_ms
            return response
        except (SandboxSecurityError, WorkspaceError, TimeoutError) as exc:
            if worker is not None:
                self.pool.discard(worker)
            elapsed = (time.time() - started) * 1000
            self.jobs[workspace.job_id].status = "error"
            self.jobs[workspace.job_id].execution_time_ms = elapsed
            return SandboxRunResponse(job_id=workspace.job_id, status="error", error=str(exc), execution_time_ms=elapsed)
        except Exception as exc:
            if worker is not None:
                self.pool.discard(worker)
            elapsed = (time.time() - started) * 1000
            self.jobs[workspace.job_id].status = "error"
            self.jobs[workspace.job_id].execution_time_ms = elapsed
            return SandboxRunResponse(job_id=workspace.job_id, status="error", error=f"sandbox execution failed: {exc}", execution_time_ms=elapsed)
        finally:
            self.workspace.cleanup_job(workspace)

    def _policy(self) -> SecurityPolicy:
        return SecurityPolicy(
            python_allowed_imports=self.settings.security.python_allowed_imports,
            javascript_allowed_imports=self.settings.security.javascript_allowed_imports,
            sql_max_limit=self.settings.limits.sql_max_limit,
        )

    def _write_program(self, workspace: JobWorkspace, language: SandboxLanguage, code: str) -> None:
        if language == SandboxLanguage.PYTHON:
            workspace.root.joinpath("main.py").write_text(code, encoding="utf-8")
        elif language == SandboxLanguage.JAVASCRIPT:
            workspace.root.joinpath("main.js").write_text(code, encoding="utf-8")
        elif language == SandboxLanguage.DUCKDB_SQL:
            runner = f"""
import json

import duckdb

sql = open('/workspace/{workspace.job_id}/query.sql', encoding='utf-8').read()
conn = duckdb.connect(':memory:')
rows = conn.execute(sql).fetchall()
columns = [d[0] for d in conn.description or []]
print(json.dumps({{'columns': columns, 'rows': rows}}, ensure_ascii=False, default=str))
""".strip()
            workspace.root.joinpath("query.sql").write_text(code, encoding="utf-8")
            workspace.root.joinpath("run_duckdb.py").write_text(runner, encoding="utf-8")

    def _execute(self, worker: Worker, workspace: JobWorkspace, language: SandboxLanguage, timeout: int, started: float) -> SandboxRunResponse:
        command = self._command(language, workspace.job_id, timeout)
        result = self.pool.exec(worker, command, workdir=f"/workspace/{workspace.job_id}", timeout_seconds=timeout)
        stdout_raw, stderr_raw = result.stdout, result.stderr
        stdout = self._decode(stdout_raw or b"")
        stderr = self._decode(stderr_raw or b"")
        truncated = False
        if len(stdout.encode("utf-8")) > self.settings.limits.max_output_bytes:
            stdout = stdout[: self.settings.limits.max_output_bytes] + "\n... [stdout truncated]"
            truncated = True
        if len(stderr.encode("utf-8")) > self.settings.limits.max_output_bytes:
            stderr = stderr[: self.settings.limits.max_output_bytes] + "\n... [stderr truncated]"
            truncated = True
        artifacts = self.workspace.collect_artifacts(workspace)
        elapsed = (time.time() - started) * 1000
        timed_out = result.exit_code == 124
        status = "ok" if result.exit_code == 0 else "error"
        parsed = self._parse_result(language, stdout) if result.exit_code == 0 else {}
        return SandboxRunResponse(
            job_id=workspace.job_id,
            status=status,
            stdout=stdout,
            stderr=stderr,
            exit_code=result.exit_code,
            execution_time_ms=elapsed,
            result=parsed,
            artifacts=artifacts,
            truncated=truncated,
            error="" if status == "ok" else (f"code execution timed out after {timeout}s" if timed_out else stderr or stdout),
        )

    def _command(self, language: SandboxLanguage, job_id: str, timeout: int) -> list[str]:
        if language == SandboxLanguage.PYTHON:
            return ["timeout", str(timeout), "python", f"/workspace/{job_id}/main.py"]
        if language == SandboxLanguage.JAVASCRIPT:
            return ["timeout", str(timeout), "node", f"/workspace/{job_id}/main.js"]
        return ["timeout", str(timeout), "python", f"/workspace/{job_id}/run_duckdb.py"]

    def _decode(self, raw: bytes) -> str:
        return raw.decode("utf-8", errors="replace")

    def _parse_result(self, language: SandboxLanguage, stdout: str) -> Dict:
        if language != SandboxLanguage.DUCKDB_SQL:
            return {}
        try:
            return json.loads(stdout.strip().splitlines()[-1])
        except Exception:
            return {}
