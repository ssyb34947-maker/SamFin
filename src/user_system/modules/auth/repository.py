"""PostgreSQL repository for authentication."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Protocol

from src.user_system.common.postgres import PostgreSQLStore

from .service import RefreshTokenRecord, UserAccount


class AuthRepository(Protocol):
    def create_user(self, *, username: str, email: str, display_name: Optional[str], password_hash: str) -> UserAccount:
        ...

    def get_user_by_identifier(self, identifier: str) -> Optional[UserAccount]:
        ...

    def get_user_by_id(self, user_id: str) -> Optional[UserAccount]:
        ...

    def get_password_hash(self, user_id: str) -> Optional[str]:
        ...

    def save_refresh_token(self, record: RefreshTokenRecord) -> None:
        ...

    def get_refresh_token(self, token_hash: str) -> Optional[RefreshTokenRecord]:
        ...

    def revoke_refresh_token(self, record: RefreshTokenRecord, *, replaced_by_token_id: Optional[str] = None) -> None:
        ...

    def record_login_event(self, *, identifier: str, success: bool, user_id: Optional[str] = None, failure_reason: Optional[str] = None) -> None:
        ...

    def update_user(self, *, user_id: str, display_name: Optional[str] = None, status: Optional[str] = None) -> UserAccount:
        ...

    def archive_user(self, *, user_id: str) -> UserAccount:
        ...


class PostgreSQLAuthRepository:
    def __init__(self, store: PostgreSQLStore):
        self.store = store

    def create_user(self, *, username: str, email: str, display_name: Optional[str], password_hash: str) -> UserAccount:
        with self.store.pool.connection() as conn:
            with conn.transaction():
                existing = self.get_user_by_identifier(username) or self.get_user_by_identifier(email)
                if existing is not None:
                    raise ValueError("username or email already exists")
                row = conn.execute(
                    """
                    INSERT INTO user_accounts (user_id, username, email, display_name)
                    VALUES ('user_' || substr(md5(random()::text || clock_timestamp()::text), 1, 12), %s, %s, %s)
                    RETURNING user_id, username, email, display_name, status, roles
                    """,
                    (username, email, display_name),
                ).fetchone()
                conn.execute(
                    """
                    INSERT INTO user_credentials (user_id, password_hash)
                    VALUES (%s, %s)
                    """,
                    (row["user_id"], password_hash),
                )
        self.store.delete_cached_pattern("auth", "user", "*")
        return self._user_from_row(row)

    def get_user_by_identifier(self, identifier: str) -> Optional[UserAccount]:
        lowered = identifier.lower()
        cached = self.store.get_cached_json("auth", "identifier", lowered)
        if cached is not None:
            return UserAccount(**cached)
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                SELECT user_id, username, email, display_name, status, roles
                FROM user_accounts
                WHERE status != 'deleted'
                  AND (lower(username) = %s OR lower(email) = %s)
                """,
                (lowered, lowered),
            ).fetchone()
        if row is None:
            return None
        user = self._user_from_row(row)
        self.store.set_cached_json(user.to_dict(), "auth", "identifier", lowered)
        self.store.set_cached_json(user.to_dict(), "auth", "user", user.user_id)
        return user

    def get_user_by_id(self, user_id: str) -> Optional[UserAccount]:
        cached = self.store.get_cached_json("auth", "user", user_id)
        if cached is not None:
            return UserAccount(**cached)
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                SELECT user_id, username, email, display_name, status, roles
                FROM user_accounts
                WHERE user_id = %s AND status != 'deleted'
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        user = self._user_from_row(row)
        self.store.set_cached_json(user.to_dict(), "auth", "user", user_id)
        return user

    def get_password_hash(self, user_id: str) -> Optional[str]:
        with self.store.pool.connection() as conn:
            row = conn.execute("SELECT password_hash FROM user_credentials WHERE user_id = %s", (user_id,)).fetchone()
        return str(row["password_hash"]) if row is not None else None

    def save_refresh_token(self, record: RefreshTokenRecord) -> None:
        with self.store.pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO auth_refresh_tokens (token_id, user_id, token_hash, jwt_id, device_id, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (record.token_id, record.user_id, record.token_hash, record.jwt_id, record.device_id, record.expires_at),
            )
        self.store.delete_cached("auth", "refresh", record.token_hash)

    def get_refresh_token(self, token_hash: str) -> Optional[RefreshTokenRecord]:
        cached = self.store.get_cached_json("auth", "refresh", token_hash)
        if cached is not None:
            return self._refresh_from_payload(cached)
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                SELECT token_id, user_id, token_hash, jwt_id, expires_at, revoked_at, replaced_by_token_id, device_id
                FROM auth_refresh_tokens
                WHERE token_hash = %s
                """,
                (token_hash,),
            ).fetchone()
        if row is None:
            return None
        record = self._refresh_from_row(row)
        self.store.set_cached_json(self._refresh_to_payload(record), "auth", "refresh", token_hash)
        return record

    def revoke_refresh_token(self, record: RefreshTokenRecord, *, replaced_by_token_id: Optional[str] = None) -> None:
        with self.store.pool.connection() as conn:
            conn.execute(
                """
                UPDATE auth_refresh_tokens
                SET revoked_at = now(), replaced_by_token_id = %s
                WHERE token_hash = %s AND revoked_at IS NULL
                """,
                (replaced_by_token_id, record.token_hash),
            )
        self.store.delete_cached("auth", "refresh", record.token_hash)

    def record_login_event(self, *, identifier: str, success: bool, user_id: Optional[str] = None, failure_reason: Optional[str] = None) -> None:
        with self.store.pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO auth_login_events (event_id, user_id, identifier, success, failure_reason)
                VALUES ('ale_' || substr(md5(random()::text || clock_timestamp()::text), 1, 12), %s, %s, %s, %s)
                """,
                (user_id, identifier, success, failure_reason),
            )

    def update_user(self, *, user_id: str, display_name: Optional[str] = None, status: Optional[str] = None) -> UserAccount:
        with self.store.pool.connection() as conn:
            row = conn.execute(
                """
                UPDATE user_accounts
                SET display_name = COALESCE(%s, display_name),
                    status = COALESCE(%s, status),
                    updated_at = now()
                WHERE user_id = %s AND status != 'deleted'
                RETURNING user_id, username, email, display_name, status, roles
                """,
                (display_name, status, user_id),
            ).fetchone()
        if row is None:
            raise ValueError("user not found")
        self.store.delete_cached("auth", "user", user_id)
        self.store.delete_cached_pattern("auth", "identifier", "*")
        return self._user_from_row(row)

    def archive_user(self, *, user_id: str) -> UserAccount:
        return self.update_user(user_id=user_id, status="deleted")

    @staticmethod
    def _user_from_row(row: Dict[str, Any]) -> UserAccount:
        return UserAccount(
            user_id=str(row["user_id"]),
            username=row.get("username"),
            email=row.get("email"),
            display_name=row.get("display_name"),
            status=str(row["status"]),
            roles=list(row.get("roles") or []),
        )

    @staticmethod
    def _refresh_from_row(row: Dict[str, Any]) -> RefreshTokenRecord:
        return RefreshTokenRecord(
            token_id=str(row["token_id"]),
            user_id=str(row["user_id"]),
            token_hash=str(row["token_hash"]),
            jwt_id=str(row["jwt_id"]),
            expires_at=row["expires_at"],
            revoked_at=row.get("revoked_at"),
            replaced_by_token_id=row.get("replaced_by_token_id"),
            device_id=row.get("device_id"),
        )

    @staticmethod
    def _refresh_to_payload(record: RefreshTokenRecord) -> Dict[str, Any]:
        return {
            "token_id": record.token_id,
            "user_id": record.user_id,
            "token_hash": record.token_hash,
            "jwt_id": record.jwt_id,
            "expires_at": record.expires_at.isoformat(),
            "revoked_at": record.revoked_at.isoformat() if record.revoked_at else None,
            "replaced_by_token_id": record.replaced_by_token_id,
            "device_id": record.device_id,
        }

    @staticmethod
    def _refresh_from_payload(payload: Dict[str, Any]) -> RefreshTokenRecord:
        return RefreshTokenRecord(
            token_id=str(payload["token_id"]),
            user_id=str(payload["user_id"]),
            token_hash=str(payload["token_hash"]),
            jwt_id=str(payload["jwt_id"]),
            expires_at=datetime.fromisoformat(str(payload["expires_at"])),
            revoked_at=datetime.fromisoformat(str(payload["revoked_at"])) if payload.get("revoked_at") else None,
            replaced_by_token_id=payload.get("replaced_by_token_id"),
            device_id=payload.get("device_id"),
        )
