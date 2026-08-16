"""Redis cache boundary for the user system."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID


class RedisDependencyError(RuntimeError):
    """Raised when redis-py is unavailable."""


class RedisConfigError(RuntimeError):
    """Raised when Redis configuration is incomplete."""


class RedisCacheClient:
    def __init__(
        self,
        *,
        url: str,
        ttl_seconds: int = 3600,
        key_prefix: str = "",
        socket_timeout: float = 2.0,
        socket_connect_timeout: float = 2.0,
        health_check_interval: int = 30,
        max_connections: int = 20,
    ):
        if not url:
            raise RedisConfigError("user_system.redis.url is required when Redis cache is enabled")
        if not key_prefix:
            raise RedisConfigError("user_system.redis.key_prefix is required when Redis cache is enabled")
        try:
            import redis
        except ModuleNotFoundError as exc:
            raise RedisDependencyError("Redis cache requires the 'redis' package.") from exc

        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix.strip(":")
        self._pool = redis.ConnectionPool.from_url(
            url,
            decode_responses=True,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            health_check_interval=health_check_interval,
            max_connections=max_connections,
        )
        self._client = redis.Redis(connection_pool=self._pool)

    def key(self, *parts: object) -> str:
        clean = [str(part).strip(":") for part in parts if str(part) != ""]
        return ":".join([self.key_prefix, *clean])

    def learning_context_key(self, *, user_id: str, class_id: str) -> str:
        return self.key("learning_context", user_id, class_id)

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set_json(self, key: str, value: Dict[str, Any], *, ttl_seconds: Optional[int] = None) -> None:
        self._client.set(
            key,
            json.dumps(value, ensure_ascii=False, default=_json_default),
            ex=ttl_seconds or self.ttl_seconds,
        )

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def delete_pattern(self, pattern: str) -> None:
        keys = list(self._client.scan_iter(match=pattern))
        if keys:
            self._client.delete(*keys)

    def close(self) -> None:
        self._client.close()
        self._pool.disconnect()


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
