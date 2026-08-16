"""MCP tools for the remote sandbox service."""

from __future__ import annotations

import json
import os
from typing import Dict

import requests
from fastmcp import FastMCP

from src.config import get_config


sandbox_mcp = FastMCP(name="sandbox")


def _sandbox_endpoint() -> str:
    endpoint = os.getenv("SANDBOX_SERVICE_URL", "")
    if endpoint:
        return endpoint.rstrip("/")
    return get_config().tool.sandbox.endpoint.rstrip("/")


def _sandbox_timeout() -> float:
    try:
        return float(os.getenv("SANDBOX_SERVICE_TIMEOUT", "") or get_config().tool.sandbox.timeout)
    except Exception:
        return 30.0


def _parse_files(files_json: str) -> Dict[str, str]:
    try:
        value = json.loads(files_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"files_json is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("files_json must be a JSON object")
    return {str(k): str(v) for k, v in value.items()}


def _run(language: str, code: str, files_json: str, timeout_seconds: int) -> str:
    endpoint = _sandbox_endpoint()
    if not endpoint:
        return json.dumps({"status": "error", "error": "sandbox endpoint is not configured"}, ensure_ascii=False)
    try:
        payload = {
            "language": language,
            "code": code,
            "files": _parse_files(files_json),
            "timeout_seconds": timeout_seconds or None,
        }
    except ValueError as exc:
        return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)
    try:
        response = requests.post(f"{endpoint}/sandbox/run", json=payload, timeout=_sandbox_timeout())
        response.raise_for_status()
        return json.dumps(response.json(), ensure_ascii=False, indent=2)
    except Exception as exc:
        return json.dumps({"status": "error", "error": f"sandbox service call failed: {exc}"}, ensure_ascii=False)




@sandbox_mcp.tool(
    name="run",
    description="""Run a restricted sandbox task through the MCP gateway.

Parameters:
- language: python, javascript, or duckdb_sql. Aliases py, js, duckdb, and sql are accepted.
- code: Python/JavaScript source code, or SQL when language is duckdb_sql.
- files_json: JSON object mapping input file names to file contents.
- timeout_seconds: execution timeout.

The MCP layer exposes one tool only. It routes to the sandbox service Python, JavaScript, or DuckDB SQL backend according to language.
""",
)
def run(language: str, code: str, files_json: str = "{}", timeout_seconds: int = 10) -> str:
    normalized = (language or "").strip().lower()
    aliases = {
        "python": "python",
        "py": "python",
        "javascript": "javascript",
        "js": "javascript",
        "duckdb": "duckdb_sql",
        "duckdb_sql": "duckdb_sql",
        "sql": "duckdb_sql",
    }
    target = aliases.get(normalized)
    if target is None:
        return json.dumps(
            {
                "status": "error",
                "error": "language must be one of: python, javascript, duckdb_sql",
            },
            ensure_ascii=False,
        )
    return _run(target, code, files_json, timeout_seconds)
