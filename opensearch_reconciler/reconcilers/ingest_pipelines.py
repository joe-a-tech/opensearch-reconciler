from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..api import OpenSearchAPI
from ..models import ManagedObject
from ..utils import ReconcileError, comparable, strip_reconciler_marker
from .base import BaseReconciler

LOG = logging.getLogger("opensearch_reconciler")


class IngestPipelineReconciler(BaseReconciler):
    kind = "ingest_pipelines"

    @staticmethod
    def _list_not_supported(exc: ReconcileError) -> bool:
        return "HTTP 404" in str(exc)

    def list_actual(self, api: OpenSearchAPI) -> Dict[str, Dict[str, Any]]:
        try:
            data = api.get_json("/_ingest/pipeline")
        except ReconcileError as exc:
            if self._list_not_supported(exc):
                LOG.debug("Ingest pipeline list endpoint unavailable; skipping delete detection for ingest_pipelines")
                return {}
            raise

        out: Dict[str, Dict[str, Any]] = {}
        for name, body in data.items():
            if isinstance(name, str) and isinstance(body, dict):
                out[name] = body
        return out

    def get_actual(self, api: OpenSearchAPI, obj: ManagedObject) -> Optional[Dict[str, Any]]:
        try:
            data = api.get_json(f"/_ingest/pipeline/{obj.name}")
        except ReconcileError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise

        body = data.get(obj.name)
        if isinstance(body, dict):
            return body
        return None

    def create(self, api: OpenSearchAPI, obj: ManagedObject) -> None:
        payload = strip_reconciler_marker(obj.body)
        api.put_json(f"/_ingest/pipeline/{obj.name}", payload)

    def update(self, api: OpenSearchAPI, obj: ManagedObject) -> None:
        self.create(api, obj)

    def delete(self, api: OpenSearchAPI, actual_key: str) -> None:
        api.delete(f"/_ingest/pipeline/{actual_key}")

    def normalise_for_compare(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return comparable(strip_reconciler_marker(data))

    @staticmethod
    def is_managed(actual: Dict[str, Any]) -> bool:
        return False