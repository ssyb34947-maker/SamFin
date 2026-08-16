"""
Shared application state helpers for the user system service.
"""

from __future__ import annotations

from fastapi import Request

from src.user_system.modules.learning.context import LearningContextService


def get_learning_service_from_request(request: Request) -> LearningContextService:
    return request.app.state.learning_context_service


def get_auth_service_from_request(request: Request):
    return request.app.state.auth_service


def get_profile_service_from_request(request: Request):
    return request.app.state.profile_service


def get_chat_service_from_request(request: Request):
    return request.app.state.chat_service


def get_exercise_service_from_request(request: Request):
    return request.app.state.exercise_service


def get_commerce_service_from_request(request: Request):
    return request.app.state.commerce_service
