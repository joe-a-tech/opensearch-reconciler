from __future__ import annotations

from typing import Any, Dict, Optional

from ..api import OpenSearchAPI, security_collection_path, security_item_path
from ..models import ManagedObject
from ..utils import ReconcileError, comparable, is_reserved_or_static, strip_reconciler_marker
from .base import BaseReconciler


class TenantReconciler(BaseReconciler):
    kind = "tenant"

    def list_actual(self, api: OpenSearchAPI) -> Dict[str, Dict[str, Any]]:
        data = api.get_json(security_collection_path("tenants"))
        out: Dict[str, Dict[str, Any]] = {}
        for name, body in data.items():
            if isinstance(body, dict):
                out[name] = body
        return out

    def get_actual(self, api: OpenSearchAPI, obj: ManagedObject) -> Optional[Dict[str, Any]]:
        try:
            data = api.get_json(security_item_path("tenants", obj.name))
            if obj.name in data and isinstance(data[obj.name], dict):
                return data[obj.name]
            return data
        except ReconcileError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise

    def create(self, api: OpenSearchAPI, obj: ManagedObject) -> None:
        payload = strip_reconciler_marker(obj.body)
        api.put_json(security_item_path("tenants", obj.name), payload)

    def update(self, api: OpenSearchAPI, obj: ManagedObject) -> None:
        self.create(api, obj)

    def delete(self, api: OpenSearchAPI, actual_key: str) -> None:
        api.delete(security_item_path("tenants", actual_key))

    def normalise_for_compare(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return comparable(strip_reconciler_marker(data))

    @staticmethod
    def is_managed(actual: Dict[str, Any]) -> bool:
        return not is_reserved_or_static(actual)