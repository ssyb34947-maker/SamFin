"""Shared PostgreSQL boundary for the user system."""

from __future__ import annotations

from typing import Iterable, Optional

from src.user_system.common.redis_cache import RedisCacheClient
from src.user_system.common.schema_check import required_table_names, verify_schema_ready


class PostgreSQLDependencyError(RuntimeError):
    """Raised when PostgreSQL dependencies are unavailable."""


class PostgreSQLConfigError(RuntimeError):
    """Raised when PostgreSQL connection configuration is incomplete."""


class PostgreSQLStore:
    REQUIRED_TABLES = required_table_names()

    def __init__(
        self,
        *,
        dsn: str,
        min_connections: int = 1,
        max_connections: int = 10,
        connect_timeout: float = 5.0,
        cache: Optional[RedisCacheClient] = None,
    ):
        if not dsn:
            raise PostgreSQLConfigError("user_system.postgres.dsn is required")
        try:
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
            from psycopg_pool import ConnectionPool
        except ModuleNotFoundError as exc:
            raise PostgreSQLDependencyError("PostgreSQL store requires 'psycopg' and 'psycopg-pool'.") from exc

        self.cache = cache
        self.jsonb = Jsonb
        self.pool = ConnectionPool(
            conninfo=dsn,
            min_size=min_connections,
            max_size=max_connections,
            kwargs={"row_factory": dict_row, "connect_timeout": connect_timeout},
        )

    def list_existing_tables(self, table_names: Iterable[str]) -> set[str]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = ANY(%s)
                """,
                (list(table_names),),
            ).fetchall()
        return {str(row["table_name"]) for row in rows}

    def verify_schema_ready(self) -> None:
        verify_schema_ready(self)

    def close(self) -> None:
        self.pool.close()
        if self.cache is not None:
            self.cache.close()

    def get_cached_json(self, *parts: object):
        if self.cache is None:
            return None
        return self.cache.get_json(self.cache.key(*parts))

    def set_cached_json(self, value, *parts: object) -> None:
        if self.cache is not None:
            self.cache.set_json(self.cache.key(*parts), value)

    def delete_cached(self, *parts: object) -> None:
        if self.cache is not None:
            self.cache.delete(self.cache.key(*parts))

    def delete_cached_pattern(self, *parts: object) -> None:
        if self.cache is not None:
            self.cache.delete_pattern(self.cache.key(*parts))
