"""Factory functions for user system services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.config.user_system import UserSystemConfig

from .common.postgres import PostgreSQLStore
from .common.redis_cache import RedisCacheClient
from .modules.auth.repository import PostgreSQLAuthRepository
from .modules.auth.service import AuthService
from .modules.chat.repository import PostgreSQLChatRepository
from .modules.chat.service import ChatService
from .modules.commerce.repository import PostgreSQLCommerceRepository
from .modules.commerce.service import CommerceService
from .modules.exercise.repository import PostgreSQLExerciseRepository
from .modules.exercise.service import ExerciseService
from .modules.learning.context import LearningContextService
from .modules.learning.postgres_repository import PostgreSQLUserLearningRepository
from .modules.profile.repository import PostgreSQLProfileRepository
from .modules.profile.service import ProfileService


class UserSystemConfigError(RuntimeError):
    """Raised when user system production configuration is incomplete."""


@dataclass
class UserSystemServices:
    store: PostgreSQLStore
    auth_service: AuthService
    profile_service: ProfileService
    learning_context_service: LearningContextService
    chat_service: ChatService
    exercise_service: ExerciseService
    commerce_service: CommerceService

    def verify_schema_ready(self) -> None:
        self.store.verify_schema_ready()

    def close(self) -> None:
        self.store.close()


def build_redis_cache(config: UserSystemConfig) -> Optional[RedisCacheClient]:
    if not config.redis.enabled:
        return None
    return RedisCacheClient(
        url=config.redis.url,
        ttl_seconds=config.redis.ttl_seconds,
        key_prefix=config.redis.key_prefix,
        socket_timeout=config.redis.socket_timeout,
        socket_connect_timeout=config.redis.socket_connect_timeout,
        health_check_interval=config.redis.health_check_interval,
        max_connections=config.redis.max_connections,
    )


def build_user_system_services(config: UserSystemConfig) -> UserSystemServices:
    if config.repository != "postgres":
        raise UserSystemConfigError("user_system.repository must be 'postgres' for the user system service")
    if not config.postgres.dsn:
        raise UserSystemConfigError("user_system.postgres.dsn is required")
    if not config.jwt.secret or not config.jwt.issuer or not config.jwt.audience:
        raise UserSystemConfigError("user_system.jwt.secret, issuer and audience are required")

    store = PostgreSQLStore(
        dsn=config.postgres.dsn,
        min_connections=config.postgres.min_connections,
        max_connections=config.postgres.max_connections,
        connect_timeout=config.postgres.connect_timeout,
        cache=build_redis_cache(config),
    )
    auth_repository = PostgreSQLAuthRepository(store)
    profile_repository = PostgreSQLProfileRepository(store)
    learning_repository = PostgreSQLUserLearningRepository(store=store)
    chat_repository = PostgreSQLChatRepository(store)
    exercise_repository = PostgreSQLExerciseRepository(store)
    commerce_repository = PostgreSQLCommerceRepository(store)

    return UserSystemServices(
        store=store,
        auth_service=AuthService(
            repository=auth_repository,
            jwt_secret=config.jwt.secret,
            issuer=config.jwt.issuer,
            audience=config.jwt.audience,
            access_minutes=config.jwt.access_minutes,
            refresh_days=config.jwt.refresh_days,
        ),
        profile_service=ProfileService(repository=profile_repository),
        learning_context_service=LearningContextService(repository=learning_repository),
        chat_service=ChatService(repository=chat_repository),
        exercise_service=ExerciseService(repository=exercise_repository),
        commerce_service=CommerceService(repository=commerce_repository),
    )


def build_learning_context_service(config: UserSystemConfig) -> LearningContextService:
    return build_user_system_services(config).learning_context_service
