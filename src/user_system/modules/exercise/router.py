"""Exercise record routes."""

from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status

from src.user_system.common.state import get_exercise_service_from_request
from src.user_system.modules.exercise.schemas import CreateExerciseAttemptRequest, UpdateExerciseAttemptRequest

router = APIRouter(prefix="/exercise", tags=["exercise"])


@router.get("/health")
def exercise_health() -> Dict[str, str]:
    return {"status": "ready", "domain": "exercise"}


@router.post("/attempts")
def create_attempt(request: Request, payload: CreateExerciseAttemptRequest):
    return get_exercise_service_from_request(request).create_exercise_attempt(**payload.model_dump())


@router.get("/attempts")
def list_attempts(request: Request, user_id: str, class_id: Optional[str] = None):
    return {"attempts": get_exercise_service_from_request(request).list_exercise_attempts(user_id=user_id, class_id=class_id)}


@router.get("/attempts/{attempt_id}")
def get_attempt(request: Request, attempt_id: str):
    try:
        return get_exercise_service_from_request(request).get_exercise_attempt(attempt_id=attempt_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/attempts/{attempt_id}")
def update_attempt(request: Request, attempt_id: str, payload: UpdateExerciseAttemptRequest):
    try:
        return get_exercise_service_from_request(request).update_attempt(attempt_id=attempt_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/attempts/{attempt_id}")
def archive_attempt(request: Request, attempt_id: str):
    try:
        return get_exercise_service_from_request(request).archive_attempt(attempt_id=attempt_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
