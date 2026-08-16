"""
Learning context routes.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from src.user_system.common.state import get_chat_service_from_request, get_learning_service_from_request, get_profile_service_from_request
from src.user_system.modules.chat.schemas import AppendMessageRequest, CreateChatRequest, UpdateChatRequest
from src.user_system.modules.learning.schemas_api import CreateClassRequest

router = APIRouter(prefix="/learning-context", tags=["learning-context"])


class ProgressRecordRequest(BaseModel):
    user_id: str
    class_id: str
    team_id: str
    source_agent: str
    record_type: str = "note"
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.post("/progress")
def append_progress_record(request: Request, payload: ProgressRecordRequest) -> Dict[str, Any]:
    return get_learning_service_from_request(request).append_progress(
        user_id=payload.user_id,
        class_id=payload.class_id,
        team_id=payload.team_id,
        source_agent=payload.source_agent,
        record_type=payload.record_type,
        content=payload.content,
        metadata=payload.metadata,
    )


@router.post("/classes")
def create_learning_class(request: Request, payload: CreateClassRequest) -> Dict[str, Any]:
    return get_profile_service_from_request(request).create_class(**payload.model_dump())


@router.post("/classes/{class_id}/chats")
def create_chat(request: Request, class_id: str, payload: CreateChatRequest) -> Dict[str, Any]:
    data = payload.model_dump()
    data["class_id"] = class_id
    return get_chat_service_from_request(request).create_chat(**data)


@router.get("/classes/{class_id}/chats")
def list_chats(request: Request, class_id: str, user_id: str, include_history: bool = True) -> Dict[str, Any]:
    return {
        "chats": get_chat_service_from_request(request).list_chats(
            user_id=user_id,
            class_id=class_id,
            include_history=include_history,
        )
    }


@router.get("/chats/{chat_id}")
def get_chat(request: Request, chat_id: str) -> Dict[str, Any]:
    try:
        return get_chat_service_from_request(request).get_chat(chat_id=chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/chats/{chat_id}")
def update_chat(request: Request, chat_id: str, payload: UpdateChatRequest) -> Dict[str, Any]:
    try:
        return get_chat_service_from_request(request).update_chat(chat_id=chat_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/chats/{chat_id}")
def archive_chat(request: Request, chat_id: str) -> Dict[str, Any]:
    try:
        return get_chat_service_from_request(request).archive_chat(chat_id=chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/chats/{chat_id}/messages")
def list_chat_messages(request: Request, chat_id: str) -> Dict[str, Any]:
    return {"messages": get_chat_service_from_request(request).list_messages(chat_id=chat_id)}


@router.post("/chats/{chat_id}/messages")
def append_chat_message(request: Request, chat_id: str, payload: AppendMessageRequest) -> Dict[str, Any]:
    try:
        return get_chat_service_from_request(request).append_message(chat_id=chat_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/chats/{chat_id}/mark-history")
def mark_chat_history(request: Request, chat_id: str) -> Dict[str, Any]:
    try:
        return get_chat_service_from_request(request).mark_chat_history(chat_id=chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{user_id}/{class_id}")
def get_learning_context(
    request: Request,
    user_id: str,
    class_id: str,
    team_id: str,
    recent_limit: int = 8,
) -> Dict[str, Any]:
    return get_learning_service_from_request(request).query_progress(
        user_id=user_id,
        class_id=class_id,
        team_id=team_id,
        recent_limit=recent_limit,
    )


@router.post("/{user_id}/{class_id}/flush")
def flush_learning_context(request: Request, user_id: str, class_id: str) -> Dict[str, int]:
    return {
        "flushed_records": get_learning_service_from_request(request).flush_context(
            user_id=user_id,
            class_id=class_id,
        )
    }


@router.post("/{user_id}/{class_id}/summary")
def save_summary(
    request: Request,
    user_id: str,
    class_id: str,
    team_id: str,
    summary: str,
    generated_by: str,
) -> Dict[str, Any]:
    item = get_learning_service_from_request(request).repository.save_summary(
        user_id=user_id,
        class_id=class_id,
        team_id=team_id,
        summary=summary,
        generated_by=generated_by,
    )
    return item.to_dict()
