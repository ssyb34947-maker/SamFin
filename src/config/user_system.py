"""
User system configuration.
"""

from dataclasses import dataclass, field


@dataclass
class RedisConfig:
    enabled: bool = False
    url: str = ""
    ttl_seconds: int = 3600
    socket_timeout: float = 2.0
    socket_connect_timeout: float = 2.0
    health_check_interval: int = 30
    max_connections: int = 20
    key_prefix: str = ""


@dataclass
class PostgreSQLConfig:
    dsn: str = ""
    min_connections: int = 1
    max_connections: int = 10
    connect_timeout: float = 5.0


@dataclass
class JWTConfig:
    secret: str = ""
    issuer: str = ""
    audience: str = ""
    access_minutes: int = 30
    refresh_days: int = 7


@dataclass
class UserSystemConfig:
    enabled: bool = True
    mode: str = "remote"  # local | remote
    base_url: str = ""
    host: str = ""
    port: int = 0
    request_timeout: float = 10.0
    repository: str = "postgres"
    jwt: JWTConfig = field(default_factory=JWTConfig)
    postgres: PostgreSQLConfig = field(default_factory=PostgreSQLConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
