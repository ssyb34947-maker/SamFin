"""
Authentication routes.
"""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, HTTPException, Request, status

from src.user_system.modules.auth.schemas import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenPair, UpdateUserRequest
from src.user_system.common.state import get_auth_service_from_request

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/health")
def auth_health() -> Dict[str, str]:
    return {"status": "ready", "domain": "auth"}


@router.post("/register", response_model=TokenPair)
def register(request: Request, payload: RegisterRequest) -> Dict[str, object]:
    try:
        return get_auth_service_from_request(request).register(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/login", response_model=TokenPair)
def login(request: Request, payload: LoginRequest) -> Dict[str, object]:
    try:
        return get_auth_service_from_request(request).login(
            identifier=payload.identifier,
            password=payload.password,
            device_id=payload.device_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/refresh", response_model=TokenPair)
def refresh(request: Request, payload: RefreshRequest) -> Dict[str, object]:
    try:
        return get_auth_service_from_request(request).refresh(payload.refresh_token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/logout")
def logout(request: Request, payload: LogoutRequest) -> Dict[str, str]:
    get_auth_service_from_request(request).logout(payload.refresh_token)
    return {"status": "ok"}


@router.get("/me")
def me(request: Request, access_token: str) -> Dict[str, object]:
    try:
        return get_auth_service_from_request(request).me(access_token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.patch("/users/{user_id}")
def update_user(request: Request, user_id: str, payload: UpdateUserRequest) -> Dict[str, object]:
    try:
        return get_auth_service_from_request(request).update_user(user_id=user_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/users/{user_id}")
def archive_user(request: Request, user_id: str) -> Dict[str, object]:
    try:
        return get_auth_service_from_request(request).archive_user(user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
