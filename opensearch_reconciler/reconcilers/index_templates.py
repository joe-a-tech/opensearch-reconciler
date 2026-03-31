from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from ..api import OpenSearchAPI
from ..models import ManagedObject
from ..utils import strip_reconciler_marker, comparable, is_reserved_or_static
from .base import BaseReconciler


def flatten_index_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    settings = copy.deepcopy(settings)
    index_block = settings.get("index")

    if isinstance(index_block, dict):
        for key, value in index_block.items():
            settings.setdefault(key, value)
        settings.pop("index", None)

    return settings


def normalise_index_setting_scalars(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: normalise_index_setting_scalars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [normalise_index_setting_scalars(v) for v in data]
    if isinstance(data, bool):
        return "true" if data else "false"
    if isinstance(data, int):
        return str(data)
    return data


class IndexTemplateReconciler(BaseReconciler):
    kind = "index_templates"

    def list_actual(self, api: OpenSearchAPI) -> Dict[str, Dict[str, Any]]:
        data = api.get_json("/_index_template")
        out: Dict[str, Dict[str, Any]] = {}
        for item in data.get("index_templates", []):
            name = item.get("name")
            body = item.get("index_template")
            if isinstance(name, str) and isinstance(body, dict):
                out[name] = body
        return out

    def get_actual(self, api: OpenSearchAPI, obj: ManagedObject) -> Optional[Dict[str, Any]]:
        if api.head(f"/_index_template/{obj.name}") == 404:
            return None
        data = api.get_json(f"/_index_template/{obj.name}")
        items = data.get("index_templates", [])
        if not items:
            return None
        return items[0].get("index_template")

    def create(self, api: OpenSearchAPI, obj: ManagedObject) -> None:
        payload = strip_reconciler_marker(obj.body)
        payload.setdefault("_meta", {})
        payload["_meta"].update(obj.body.get("_reconciler", {}))
        api.put_json(f"/_index_template/{obj.name}", payload)

    def update(self, api: OpenSearchAPI, obj: ManagedObject) -> None:
        self.create(api, obj)

    def delete(self, api: OpenSearchAPI, actual_key: str) -> None:
        api.delete(f"/_index_template/{actual_key}")

    def normalise_for_compare(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = copy.deepcopy(data)
        reconciler_meta = data.pop("_reconciler", None)

        data.setdefault("_meta", {})
        if isinstance(reconciler_meta, dict):
            data["_meta"].update(reconciler_meta)

        data.pop("data_stream", None)

        template = data.get("template")
        if isinstance(template, dict):
            settings = template.get("settings")
            if isinstance(settings, dict):
                settings = flatten_index_settings(settings)
                settings = normalise_index_setting_scalars(settings)
                template["settings"] = settings

                if not settings:
                    template.pop("settings", None)

            if not template:
                data.pop("template", None)

        return comparable(data)

    @staticmethod
    def is_managed(actual: Dict[str, Any]) -> bool:
        meta = actual.get("_meta", {})
        if not isinstance(meta, dict):
            return False
        if is_reserved_or_static(meta):
            return False
        return meta.get("managed") is True