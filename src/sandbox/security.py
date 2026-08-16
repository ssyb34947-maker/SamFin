"""Static safety checks before code is sent to Docker."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Iterable

from .schemas import SandboxLanguage


class SandboxSecurityError(ValueError):
    """Raised when submitted code violates sandbox policy."""


PYTHON_FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "__import__", "globals", "locals", "vars", "input", "help",
}
PYTHON_FORBIDDEN_IMPORTS = {
    "asyncio", "builtins", "ctypes", "importlib", "inspect", "multiprocessing", "os", "pathlib",
    "pickle", "platform", "pty", "pwd", "requests", "resource", "shutil", "signal", "socket",
    "subprocess", "sys", "threading", "urllib",
}
JS_FORBIDDEN_PATTERNS = [
    r"\beval\s*\(", r"\bFunction\s*\(", r"new\s+Function\s*\(", r"\brequire\s*\(",
    r"\bimport\s+", r"child_process", r"\bfs\b", r"\bnet\b", r"\bhttp\b", r"\bprocess\b",
]
SQL_FORBIDDEN_KEYWORDS = {
    "alter", "attach", "copy", "create", "delete", "detach", "drop", "insert", "install",
    "load", "pragma", "replace", "set", "update", "vacuum",
}


@dataclass(frozen=True)
class SecurityPolicy:
    python_allowed_imports: Iterable[str]
    javascript_allowed_imports: Iterable[str]
    sql_max_limit: int


def validate_code(language: SandboxLanguage, code: str, policy: SecurityPolicy) -> str:
    if language == SandboxLanguage.PYTHON:
        _validate_python(code, set(policy.python_allowed_imports))
        return code
    if language == SandboxLanguage.JAVASCRIPT:
        _validate_javascript(code)
        return code
    if language == SandboxLanguage.DUCKDB_SQL:
        return _validate_sql(code, policy.sql_max_limit)
    raise SandboxSecurityError(f"unsupported language: {language}")


def _validate_python(code: str, allowed_imports: set[str]) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise SandboxSecurityError(f"Python syntax error: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in PYTHON_FORBIDDEN_IMPORTS or root not in allowed_imports:
                    raise SandboxSecurityError(f"Python import is not allowed: {root}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if not root or root in PYTHON_FORBIDDEN_IMPORTS or root not in allowed_imports:
                raise SandboxSecurityError(f"Python import is not allowed: {root}")
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in PYTHON_FORBIDDEN_NAMES:
                raise SandboxSecurityError(f"Python call is not allowed: {name}")


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _validate_javascript(code: str) -> None:
    for pattern in JS_FORBIDDEN_PATTERNS:
        if re.search(pattern, code):
            raise SandboxSecurityError(f"JavaScript pattern is not allowed: {pattern}")


def _validate_sql(sql: str, max_limit: int) -> str:
    stripped = sql.strip().rstrip(";")
    if not stripped:
        raise SandboxSecurityError("SQL must not be empty")
    if ";" in stripped:
        raise SandboxSecurityError("SQL must contain exactly one statement")
    lowered = stripped.lower()
    if not lowered.startswith("select") and not lowered.startswith("with"):
        raise SandboxSecurityError("Only SELECT queries are allowed")
    tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", lowered))
    blocked = sorted(tokens & SQL_FORBIDDEN_KEYWORDS)
    if blocked:
        raise SandboxSecurityError(f"SQL keyword is not allowed: {blocked[0]}")
    if re.search(r"select\s+\*", lowered) or re.search(r",\s*\*", lowered):
        raise SandboxSecurityError("SELECT * is not allowed; list columns explicitly")
    limit_match = re.search(r"\blimit\s+(\d+)\b", lowered)
    if limit_match and int(limit_match.group(1)) > max_limit:
        raise SandboxSecurityError(f"SQL LIMIT must be <= {max_limit}")
    if not limit_match:
        stripped = f"{stripped} LIMIT {max_limit}"
    return stripped
