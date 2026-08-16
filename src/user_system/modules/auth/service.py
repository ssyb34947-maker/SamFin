"""Authentication service for the standalone user system."""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


@dataclass
class UserAccount:
    user_id: str
    username: Optional[str]
    email: Optional[str]
    display_name: Optional[str] = None
    status: str = "active"
    roles: list[str] = field(default_factory=lambda: ["student"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "status": self.status,
            "roles": list(self.roles),
        }


@dataclass
class RefreshTokenRecord:
    token_id: str
    user_id: str
    token_hash: str
    jwt_id: str
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    replaced_by_token_id: Optional[str] = None
    device_id: Optional[str] = None


class AuthConfigError(RuntimeError):
    """Raised when JWT configuration is incomplete."""


class AuthRepositoryMissingError(RuntimeError):
    """Raised when AuthService is constructed without a repository."""


class AuthService:
    def __init__(
        self,
        *,
        repository,
        jwt_secret: Optional[str] = None,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        access_minutes: int = 30,
        refresh_days: int = 7,
    ):
        if repository is None:
            raise AuthRepositoryMissingError("AuthService requires a persistent repository")
        self.repository = repository
        self.jwt_secret = jwt_secret if jwt_secret is not None else os.getenv("USER_SYSTEM_JWT_SECRET", "")
        self.issuer = issuer if issuer is not None else os.getenv("USER_SYSTEM_JWT_ISSUER", "")
        self.audience = audience if audience is not None else os.getenv("USER_SYSTEM_JWT_AUDIENCE", "")
        if not self.jwt_secret or not self.issuer or not self.audience:
            raise AuthConfigError("USER_SYSTEM_JWT_SECRET, USER_SYSTEM_JWT_ISSUER and USER_SYSTEM_JWT_AUDIENCE are required")
        self.access_minutes = access_minutes
        self.refresh_days = refresh_days
        self.password_hasher = PasswordHasher()

    def hash_password(self, password: str) -> str:
        return self.password_hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return self.password_hasher.verify(password_hash, password)
        except VerifyMismatchError:
            return False

    def register(self, *, username: str, email: str, password: str, display_name: Optional[str] = None, device_id: Optional[str] = None) -> Dict[str, Any]:
        user = self.repository.create_user(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=self.hash_password(password),
        )
        return self._issue_token_pair(user, device_id=device_id)

    def login(self, *, identifier: str, password: str, device_id: Optional[str] = None) -> Dict[str, Any]:
        user = self.repository.get_user_by_identifier(identifier)
        password_hash = self.repository.get_password_hash(user.user_id) if user is not None else None
        if user is None or password_hash is None or not self.verify_password(password, password_hash):
            self.repository.record_login_event(identifier=identifier, success=False, failure_reason="invalid credentials")
            raise ValueError("invalid credentials")
        if user.status != "active":
            self.repository.record_login_event(identifier=identifier, user_id=user.user_id, success=False, failure_reason="user is not active")
            raise ValueError("user is not active")
        self.repository.record_login_event(identifier=identifier, user_id=user.user_id, success=True)
        return self._issue_token_pair(user, device_id=device_id)

    def refresh(self, refresh_token: str) -> Dict[str, Any]:
        payload = self.decode_token(refresh_token, expected_type="refresh")
        record = self.repository.get_refresh_token(self._hash_token(refresh_token))
        if record is None or record.revoked_at is not None or record.expires_at <= utc_now():
            raise ValueError("refresh token is not active")
        user = self.repository.get_user_by_id(str(payload["sub"]))
        if user is None or user.status != "active":
            raise ValueError("user is not active")
        pair = self._issue_token_pair(user, device_id=record.device_id)
        new_record = self.repository.get_refresh_token(self._hash_token(pair["refresh_token"]))
        self.repository.revoke_refresh_token(record, replaced_by_token_id=new_record.token_id if new_record else None)
        return pair

    def logout(self, refresh_token: str) -> None:
        record = self.repository.get_refresh_token(self._hash_token(refresh_token))
        if record is not None and record.revoked_at is None:
            self.repository.revoke_refresh_token(record)

    def me(self, access_token: str) -> Dict[str, Any]:
        payload = self.decode_token(access_token, expected_type="access")
        user = self.repository.get_user_by_id(str(payload["sub"]))
        if user is None or user.status != "active":
            raise ValueError("user is not active")
        return user.to_dict()

    def update_user(self, *, user_id: str, display_name: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        return self.repository.update_user(user_id=user_id, display_name=display_name, status=status).to_dict()

    def archive_user(self, *, user_id: str) -> Dict[str, Any]:
        return self.repository.archive_user(user_id=user_id).to_dict()

    def decode_token(self, token: str, *, expected_type: str) -> Dict[str, Any]:
        payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"], issuer=self.issuer, audience=self.audience)
        if payload.get("type") != expected_type or not payload.get("jti"):
            raise ValueError("invalid token type")
        return payload

    def _issue_token_pair(self, user: UserAccount, *, device_id: Optional[str]) -> Dict[str, Any]:
        now = utc_now()
        access_jti = f"at_{uuid.uuid4().hex}"
        refresh_jti = f"rt_{uuid.uuid4().hex}"
        access_exp = now + timedelta(minutes=self.access_minutes)
        refresh_exp = now + timedelta(days=self.refresh_days)
        access_token = self._encode(user=user, token_type="access", jwt_id=access_jti, now=now, expires_at=access_exp)
        refresh_token = self._encode(user=user, token_type="refresh", jwt_id=refresh_jti, now=now, expires_at=refresh_exp)
        self.repository.save_refresh_token(
            RefreshTokenRecord(
                token_id=f"rtok_{uuid.uuid4().hex[:12]}",
                user_id=user.user_id,
                token_hash=self._hash_token(refresh_token),
                jwt_id=refresh_jti,
                expires_at=refresh_exp,
                device_id=device_id,
            )
        )
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer", "expires_in": self.access_minutes * 60}

    def _encode(self, *, user: UserAccount, token_type: str, jwt_id: str, now: datetime, expires_at: datetime) -> str:
        return jwt.encode(
            {
                "sub": user.user_id,
                "iss": self.issuer,
                "aud": self.audience,
                "iat": int(now.timestamp()),
                "nbf": int(now.timestamp()),
                "exp": int(expires_at.timestamp()),
                "jti": jwt_id,
                "type": token_type,
                "roles": list(user.roles),
            },
            self.jwt_secret,
            algorithm="HS256",
        )

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
