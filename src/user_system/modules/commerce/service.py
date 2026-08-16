"""Commerce order and entitlement service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class CommerceService:
    def __init__(self, *, repository):
        if repository is None:
            raise RuntimeError("CommerceService requires a persistent repository")
        self.repository = repository

    def create_order(self, **payload) -> Dict[str, Any]:
        return self.repository.create_order(**payload)

    def get_order(self, *, order_id: str) -> Dict[str, Any]:
        item = self.repository.get_order(order_id=order_id)
        if item is None:
            raise ValueError("order not found")
        return item

    def list_orders(self, *, user_id: str) -> List[Dict[str, Any]]:
        return self.repository.list_orders(user_id=user_id)

    def update_order(self, *, order_id: str, status: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.repository.update_order(order_id=order_id, status=status, metadata=metadata)

    def archive_order(self, *, order_id: str) -> Dict[str, Any]:
        return self.repository.update_order(order_id=order_id, status="cancelled")

    def create_entitlement(self, **payload) -> Dict[str, Any]:
        return self.repository.create_entitlement(**payload)

    def get_entitlement(self, *, entitlement_id: str) -> Dict[str, Any]:
        item = self.repository.get_entitlement(entitlement_id=entitlement_id)
        if item is None:
            raise ValueError("entitlement not found")
        return item

    def list_entitlements(self, *, user_id: str) -> List[Dict[str, Any]]:
        return self.repository.list_entitlements(user_id=user_id)

    def update_entitlement(self, *, entitlement_id: str, status: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.repository.update_entitlement(entitlement_id=entitlement_id, status=status, metadata=metadata)

    def archive_entitlement(self, *, entitlement_id: str) -> Dict[str, Any]:
        return self.repository.update_entitlement(entitlement_id=entitlement_id, status="revoked")
