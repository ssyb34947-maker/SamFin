"""Auth API schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    identifier: str
    password: str
    device_id: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    status: Optional[str] = None


class UserAccountResponse(BaseModel):
    user_id: str
    username: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    status: str
    roles: List[str] = Field(default_factory=list)
