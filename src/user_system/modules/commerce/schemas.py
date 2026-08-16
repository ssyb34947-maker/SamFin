"""Commerce API schemas."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CreateOrderRequest(BaseModel):
    user_id: str
    product_id: str
    product_type: str
    amount_cents: int = 0
    currency: str = "CNY"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateOrderRequest(BaseModel):
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CreateEntitlementRequest(BaseModel):
    user_id: str
    team_id: str
    class_id: Optional[str] = None
    order_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateEntitlementRequest(BaseModel):
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
