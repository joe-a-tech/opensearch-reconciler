from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from ..api import OpenSearchAPI
from ..models import ManagedObject
from ..utils import ReconcileError, comparable, strip_reconciler_marker
from .base import BaseReconciler


def normalise_ism_policy_defaults(data: Any) -> Any:
    if isinstance(data, dict):
        data = {k: normalise_ism_policy_defaults(v) for k, v in data.items()}

        retry = data.get("retry")
        if isinstance(retry, dict):
            if retry == {
                "count": 3,
                "backoff": "exponential",
                "delay": "1m",
            }:
                data.pop("retry", None)

        return data

    if isinstance(data, list):
        return [normalise_ism_policy_defaults(v) for v in data]

    return data


class ISMPolicyReconciler(BaseReconciler):
    kind = "ism_policies"

    @staticmethod
    def _is_missing_ism_index_error(exc: ReconcileError) -> bool:
        msg = str(exc)
        return "HTTP 404" in msg and ".opendistro-ism-config" in msg

    @staticmethod
    def _extract_policy_doc(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        policy_wrapper = data.get("policy")
        if not isinstance(policy_wrapper, dict):
            return None

        if "policy" in policy_wrapper and isinstance(policy_wrapper["policy"], dict):
            return policy_wrapper["policy"]

        return policy_wrapper

    def list_actual(self, api: OpenSearchAPI) -> Dict[str, Dict[str, Any]]:
        try:
            data = api.get_json("/_plugins/_ism/policies")
        except ReconcileError as exc:
            if self._is_missing_ism_index_error(exc):
                return {}
            raise

        out: Dict[str, Dict[str, Any]] = {}
        for item in data.get("policies", []):
            if not isinstance(item, dict):
                continue
            policy_id = item.get("_id")
            policy = item.get("policy")
            if isinstance(policy_id, str) and isinstance(policy, dict):
                out[policy_id] = policy
        return out

    def get_actual(self, api: OpenSearchAPI, obj: ManagedObject) -> Optional[Dict[str, Any]]:
        try:
            data = api.get_json(f"/_plugins/_ism/policies/{obj.name}")
            return self._extract_policy_doc(data)
        except ReconcileError as exc:
            msg = str(exc)
            if "HTTP 404" in msg or ".opendistro-ism-config" in msg:
                return None
            raise

    def create(self, api: OpenSearchAPI, obj: ManagedObject) -> None:
        payload = strip_reconciler_marker(obj.body)
        payload.setdefault("description", "")
        marker = f" [managed customer={obj.customer}]"
        if marker not in payload["description"]:
            payload["description"] = (payload["description"] + marker).strip()
        api.put_json(f"/_plugins/_ism/policies/{obj.name}", {"policy": payload})

    def update(self, api: OpenSearchAPI, obj: ManagedObject) -> None:
        current = api.get_json(f"/_plugins/_ism/policies/{obj.name}")
        seq_no = current.get("_seq_no")
        primary_term = current.get("_primary_term")

        if not isinstance(seq_no, int) or not isinstance(primary_term, int):
            raise ReconcileError(
                f"ISM policy {obj.name} is missing _seq_no/_primary_term in GET response"
            )

        payload = strip_reconciler_marker(obj.body)
        payload.setdefault("description", "")
        marker = f" [managed customer={obj.customer}]"
        if marker not in payload["description"]:
            payload["description"] = (payload["description"] + marker).strip()

        path = f"/_plugins/_ism/policies/{obj.name}?if_seq_no={seq_no}&if_primary_term={primary_term}"
        api.put_json(path, {"policy": payload})

    def delete(self, api: OpenSearchAPI, actual_key: str) -> None:
        api.delete(f"/_plugins/_ism/policies/{actual_key}")

    def normalise_for_compare(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = copy.deepcopy(data)
        reconciler_meta = data.pop("_reconciler", None)

        if "policy" in data and isinstance(data["policy"], dict):
            data = copy.deepcopy(data["policy"])

        data.setdefault("description", "")
        if isinstance(reconciler_meta, dict):
            marker = f" [managed customer={reconciler_meta['customer']}]"
            if marker not in data["description"]:
                data["description"] = (data["description"] + marker).strip()

        if isinstance(data.get("ism_template"), dict):
            data["ism_template"] = [data["ism_template"]]

        data = normalise_ism_policy_defaults(data)

        return comparable(data)

    @staticmethod
    def is_managed(actual: Dict[str, Any]) -> bool:
        if "policy" in actual and isinstance(actual["policy"], dict):
            actual = actual["policy"]
        description = actual.get("description", "")
        return isinstance(description, str) and "[managed customer=" in description