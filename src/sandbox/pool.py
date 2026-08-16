"""Warm Docker worker pool for sandbox execution."""

from __future__ import annotations

import queue
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import SandboxDockerConfig, SandboxPoolConfig


@dataclass(frozen=True)
class Worker:
    container_id: str
    created_at: float


@dataclass(frozen=True)
class DockerExecResult:
    exit_code: int
    stdout: bytes
    stderr: bytes


class DockerWorkerPool:
    def __init__(self, docker_config: SandboxDockerConfig, pool_config: SandboxPoolConfig, workspace_root: Path):
        self.docker_config = docker_config
        self.pool_config = pool_config
        self.workspace_root = workspace_root
        self._queue: queue.Queue[Worker] = queue.Queue(maxsize=max(pool_config.size, 1))
        self._closed = False
        self._lock = threading.Lock()

    def start(self) -> None:
        for _ in range(max(self.pool_config.size, 1)):
            self._queue.put(self._create_worker())

    def acquire(self) -> Worker:
        try:
            return self._queue.get(timeout=self.pool_config.acquire_timeout_seconds)
        except queue.Empty as exc:
            raise TimeoutError("sandbox worker pool is busy") from exc

    def release(self, worker: Worker) -> None:
        if self._closed:
            self._remove(worker)
            return
        self._queue.put(worker)

    def discard(self, worker: Optional[Worker]) -> None:
        if worker is not None:
            self._remove(worker)
        if not self._closed:
            self._queue.put(self._create_worker())

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
        while True:
            try:
                worker = self._queue.get_nowait()
            except queue.Empty:
                break
            self._remove(worker)

    def exec(self, worker: Worker, command: list[str], workdir: str, timeout_seconds: int) -> DockerExecResult:
        cmd = [
            "docker", "exec", "--user", self.docker_config.user, "--workdir", workdir,
            worker.container_id, *command,
        ]
        completed = subprocess.run(cmd, capture_output=True, timeout=timeout_seconds + 2)
        return DockerExecResult(exit_code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)

    @property
    def size(self) -> int:
        return self._queue.qsize()

    def _create_worker(self) -> Worker:
        name = f"samlang-sandbox-worker-{uuid.uuid4().hex[:12]}"
        cmd = [
            "docker", "run", "-d",
            "--name", name,
            "--memory", self.docker_config.memory_limit,
            "--cpus", str(max(self.docker_config.nano_cpus / 1_000_000_000, 0.1)),
            "--pids-limit", str(self.docker_config.pids_limit),
            "--user", self.docker_config.user,
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-v", f"{self.workspace_root.resolve()}:/workspace:rw",
            "-w", "/workspace",
            "--label", "samlang.service=sandbox",
            "--label", "samlang.role=worker",
        ]
        if self.docker_config.network_disabled:
            cmd.extend(["--network", "none"])
        if self.docker_config.read_only_root:
            cmd.append("--read-only")
        cmd.extend([self.docker_config.runtime_image, "sleep", "infinity"])
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return Worker(container_id=completed.stdout.strip(), created_at=time.time())

    def _remove(self, worker: Worker) -> None:
        subprocess.run(["docker", "rm", "-f", worker.container_id], capture_output=True)
