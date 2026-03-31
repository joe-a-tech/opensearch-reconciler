from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from ..api import OpenSearchAPI
from ..models import ManagedObject
from ..utils import comparable, first_diff, is_reserved_or_static


class BaseReconciler:
    kind: str

    def list_actual(self, api: OpenSearchAPI) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError

    def get_actual(self, api: OpenSearchAPI, obj: ManagedObject) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def create(self, api: OpenSearchAPI, obj: ManagedObject) -> None:
        raise NotImplementedError

    def update(self, api: OpenSearchAPI, obj: ManagedObject) -> None:
        raise NotImplementedError

    def delete(self, api: OpenSearchAPI, actual_key: str) -> None:
        raise NotImplementedError

    def normalise_for_compare(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return comparable(copy.deepcopy(data))

    def objects_differ(self, desired: Dict[str, Any], actual: Dict[str, Any]) -> bool:
        return self.normalise_for_compare(desired) != self.normalise_for_compare(actual)

    def diff_summary(self, desired: Dict[str, Any], actual: Dict[str, Any], show_diff: bool = False) -> str:
        desired_cmp = self.normalise_for_compare(desired)
        actual_cmp = self.normalise_for_compare(actual)

        if desired_cmp == actual_cmp:
            return ""

        if show_diff:
            diff = first_diff(desired_cmp, actual_cmp)
            if diff:
                return diff

        return f"{self.kind} differs"

    @staticmethod
    def is_managed(actual: Dict[str, Any]) -> bool:
        if is_reserved_or_static(actual):
            return False
        meta = actual.get("_reconciler", {})
        return isinstance(meta, dict) and meta.get("managed") is True