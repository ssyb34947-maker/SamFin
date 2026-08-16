"""Workspace and artifact handling for sandbox jobs."""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .schemas import Artifact


class WorkspaceError(ValueError):
    pass


@dataclass(frozen=True)
class JobWorkspace:
    job_id: str
    root: Path
    input_dir: Path
    output_dir: Path


class WorkspaceManager:
    def __init__(self, workspace_root: Path, artifact_root: Path, max_file_bytes: int, max_artifacts: int, max_artifact_bytes: int):
        self.workspace_root = workspace_root
        self.artifact_root = artifact_root
        self.max_file_bytes = max_file_bytes
        self.max_artifacts = max_artifacts
        self.max_artifact_bytes = max_artifact_bytes
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.artifact_root.mkdir(parents=True, exist_ok=True)

    def create_job(self) -> JobWorkspace:
        job_id = uuid.uuid4().hex
        root = self.workspace_root / job_id
        input_dir = root / "input"
        output_dir = root / "output"
        input_dir.mkdir(parents=True, exist_ok=False)
        output_dir.mkdir(parents=True, exist_ok=False)
        root.chmod(0o777)
        input_dir.chmod(0o777)
        output_dir.chmod(0o777)
        return JobWorkspace(job_id=job_id, root=root, input_dir=input_dir, output_dir=output_dir)

    def write_files(self, workspace: JobWorkspace, files: Dict[str, str]) -> None:
        for name, content in files.items():
            safe_name = self._safe_relative_path(name)
            raw = content.encode("utf-8")
            if len(raw) > self.max_file_bytes:
                raise WorkspaceError(f"input file is too large: {name}")
            target = workspace.input_dir / safe_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            target.chmod(0o666)

    def collect_artifacts(self, workspace: JobWorkspace) -> List[Artifact]:
        artifacts: List[Artifact] = []
        if not workspace.output_dir.exists():
            return artifacts
        for path in sorted(p for p in workspace.output_dir.rglob("*") if p.is_file()):
            if len(artifacts) >= self.max_artifacts:
                break
            size = path.stat().st_size
            if size > self.max_artifact_bytes:
                continue
            artifact_id = uuid.uuid4().hex
            rel_name = path.relative_to(workspace.output_dir).as_posix()
            store_dir = self.artifact_root / artifact_id
            store_dir.mkdir(parents=True, exist_ok=False)
            stored = store_dir / Path(rel_name).name
            shutil.copy2(path, stored)
            artifacts.append(Artifact(artifact_id=artifact_id, filename=rel_name, size_bytes=size, download_path=f"/sandbox/artifacts/{artifact_id}"))
        return artifacts

    def artifact_path(self, artifact_id: str) -> Path:
        if not artifact_id or not artifact_id.isalnum():
            raise WorkspaceError("invalid artifact id")
        root = self.artifact_root / artifact_id
        files = [p for p in root.iterdir() if p.is_file()] if root.exists() else []
        if not files:
            raise FileNotFoundError(artifact_id)
        return files[0]

    def cleanup_job(self, workspace: JobWorkspace) -> None:
        shutil.rmtree(workspace.root, ignore_errors=True)

    def _safe_relative_path(self, name: str) -> Path:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or not path.name:
            raise WorkspaceError(f"unsafe file path: {name}")
        return path
