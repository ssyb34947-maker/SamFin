"""User profile and account record routes."""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, HTTPException, Request, status

from src.user_system.common.state import get_profile_service_from_request
from src.user_system.modules.profile.schemas import UpdateClassRequest, UpdateProfileRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/health")
def profile_health() -> Dict[str, str]:
    return {"status": "ready", "domain": "profile"}


@router.get("/{user_id}/profile")
def get_profile(request: Request, user_id: str):
    try:
        return get_profile_service_from_request(request).get_profile(user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{user_id}/profile")
def upsert_profile(request: Request, user_id: str, payload: UpdateProfileRequest):
    return get_profile_service_from_request(request).upsert_profile(user_id=user_id, display_name=payload.display_name, profile=payload.profile)


@router.get("/{user_id}/classes")
def list_user_classes(request: Request, user_id: str, status: str = "active"):
    return {"classes": get_profile_service_from_request(request).list_classes(user_id=user_id, status=status)}


@router.get("/{user_id}/classes/{class_id}")
def get_user_class(request: Request, user_id: str, class_id: str):
    try:
        return get_profile_service_from_request(request).get_class(user_id=user_id, class_id=class_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{user_id}/classes/{class_id}")
def update_user_class(request: Request, user_id: str, class_id: str, payload: UpdateClassRequest):
    try:
        return get_profile_service_from_request(request).update_class(user_id=user_id, class_id=class_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{user_id}/classes/{class_id}")
def archive_user_class(request: Request, user_id: str, class_id: str):
    try:
        return get_profile_service_from_request(request).archive_class(user_id=user_id, class_id=class_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
