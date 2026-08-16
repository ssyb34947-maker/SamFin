"""
Module-level schema readiness checks for the user system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Protocol, Sequence


@dataclass(frozen=True)
class SchemaModule:
    name: str
    sql_file: str
    tables: Sequence[str]


USER_SYSTEM_SCHEMA_MODULES = (
    SchemaModule("auth", "sql/user_system/001_auth.sql", ("user_accounts", "user_credentials", "auth_refresh_tokens", "auth_login_events")),
    SchemaModule("learning", "sql/user_system/002_learning.sql", ("user_profiles", "learning_classes", "learning_progress_records", "learning_summaries")),
    SchemaModule("chat", "sql/user_system/003_chat.sql", ("learning_chats", "learning_chat_messages")),
    SchemaModule("exercise", "sql/user_system/004_exercise.sql", ("exercise_attempts", "exercise_attempt_items")),
    SchemaModule("commerce", "sql/user_system/005_commerce.sql", ("purchase_orders", "course_entitlements")),
)


class SchemaCheckError(RuntimeError):
    def __init__(self, missing_by_module: Dict[str, List[str]], sql_files: Dict[str, str]):
        self.missing_by_module = missing_by_module
        self.sql_files = sql_files
        parts = []
        for module_name, tables in missing_by_module.items():
            parts.append(f"{module_name} module missing tables: {', '.join(tables)}; run {sql_files[module_name]}")
        super().__init__("User system database schema is not ready. " + " | ".join(parts))


class TableIntrospector(Protocol):
    def list_existing_tables(self, table_names: Iterable[str]) -> set[str]:
        ...


def required_table_names() -> tuple[str, ...]:
    names: list[str] = []
    for module in USER_SYSTEM_SCHEMA_MODULES:
        names.extend(module.tables)
    return tuple(dict.fromkeys(names))


def validate_schema_modules(existing_tables: Iterable[str]) -> None:
    existing = set(existing_tables)
    missing_by_module: Dict[str, List[str]] = {}
    sql_files: Dict[str, str] = {}
    for module in USER_SYSTEM_SCHEMA_MODULES:
        missing = [table for table in module.tables if table not in existing]
        if missing:
            missing_by_module[module.name] = missing
            sql_files[module.name] = module.sql_file
    if missing_by_module:
        raise SchemaCheckError(missing_by_module, sql_files)


def verify_schema_ready(introspector: TableIntrospector) -> None:
    validate_schema_modules(introspector.list_existing_tables(required_table_names()))
