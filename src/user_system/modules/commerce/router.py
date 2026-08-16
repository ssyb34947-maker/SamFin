"""Purchase and entitlement routes."""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, HTTPException, Request, status

from src.user_system.common.state import get_commerce_service_from_request
from src.user_system.modules.commerce.schemas import CreateEntitlementRequest, CreateOrderRequest, UpdateEntitlementRequest, UpdateOrderRequest

router = APIRouter(prefix="/commerce", tags=["commerce"])


@router.get("/health")
def commerce_health() -> Dict[str, str]:
    return {"status": "ready", "domain": "commerce"}


@router.post("/orders")
def create_order(request: Request, payload: CreateOrderRequest):
    return get_commerce_service_from_request(request).create_order(**payload.model_dump())


@router.get("/orders")
def list_orders(request: Request, user_id: str):
    return {"orders": get_commerce_service_from_request(request).list_orders(user_id=user_id)}


@router.get("/orders/{order_id}")
def get_order(request: Request, order_id: str):
    try:
        return get_commerce_service_from_request(request).get_order(order_id=order_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/orders/{order_id}")
def update_order(request: Request, order_id: str, payload: UpdateOrderRequest):
    try:
        return get_commerce_service_from_request(request).update_order(order_id=order_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/orders/{order_id}")
def archive_order(request: Request, order_id: str):
    try:
        return get_commerce_service_from_request(request).archive_order(order_id=order_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/entitlements")
def create_entitlement(request: Request, payload: CreateEntitlementRequest):
    return get_commerce_service_from_request(request).create_entitlement(**payload.model_dump())


@router.get("/entitlements")
def list_entitlements(request: Request, user_id: str):
    return {"entitlements": get_commerce_service_from_request(request).list_entitlements(user_id=user_id)}


@router.get("/entitlements/{entitlement_id}")
def get_entitlement(request: Request, entitlement_id: str):
    try:
        return get_commerce_service_from_request(request).get_entitlement(entitlement_id=entitlement_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/entitlements/{entitlement_id}")
def update_entitlement(request: Request, entitlement_id: str, payload: UpdateEntitlementRequest):
    try:
        return get_commerce_service_from_request(request).update_entitlement(entitlement_id=entitlement_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/entitlements/{entitlement_id}")
def archive_entitlement(request: Request, entitlement_id: str):
    try:
        return get_commerce_service_from_request(request).archive_entitlement(entitlement_id=entitlement_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
