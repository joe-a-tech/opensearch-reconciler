from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional


class ReconcileError(Exception):
    pass


def strip_reconciler_marker(data: Dict[str, Any]) -> Dict[str, Any]:
    data = copy.deepcopy(data)
    data.pop("_reconciler", None)
    return data


def annotate_managed(obj: Dict[str, Any], customer: str, kind: str, name: str) -> Dict[str, Any]:
    body = copy.deepcopy(obj)
    meta = body.setdefault("_reconciler", {})
    if not isinstance(meta, dict):
        raise ReconcileError(f"_reconciler must be an object for {kind}/{name}")
    meta.setdefault("managed", True)
    meta.setdefault("customer", customer)
    meta.setdefault("kind", kind)
    meta.setdefault("name", name)
    return body


def scrub_runtime_fields(data: Any) -> Any:
    if isinstance(data, dict):
        clean = {}
        for key, value in data.items():
            if key in {
                "static",
                "reserved",
                "hidden",
                "_seq_no",
                "_primary_term",
                "_version",
                "created_at",
                "last_updated_time",
                "policy_id",
                "schema_version",
                "error_notification",
            }:
                continue
            clean[key] = scrub_runtime_fields(value)
        return clean
    if isinstance(data, list):
        return [scrub_runtime_fields(v) for v in data]
    return data


def prune_empty_values(data: Any) -> Any:
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            value = prune_empty_values(value)
            if value in ({}, [], "", None):
                continue
            cleaned[key] = value
        return cleaned
    if isinstance(data, list):
        return [prune_empty_values(v) for v in data]
    return data


def sort_nested(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: sort_nested(data[k]) for k in sorted(data)}
    if isinstance(data, list):
        normalised = [sort_nested(v) for v in data]
        return sorted(
            normalised,
            key=lambda x: json.dumps(x, sort_keys=True, separators=(",", ":")),
        )
    return data


def comparable(data: Dict[str, Any]) -> Dict[str, Any]:
    return sort_nested(prune_empty_values(scrub_runtime_fields(copy.deepcopy(data))))


def is_reserved_or_static(actual: Dict[str, Any]) -> bool:
    return any(actual.get(flag) is True for flag in ("reserved", "static", "hidden"))


def short_repr(value: Any, limit: int = 160) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def format_path(path: List[str]) -> str:
    if not path:
        return "<root>"
    out = []
    for part in path:
        if part.startswith("[") and out:
            out[-1] = out[-1] + part
        else:
            out.append(part)
    return ".".join(out)


def first_diff(desired: Any, actual: Any, path: Optional[List[str]] = None) -> Optional[str]:
    if path is None:
        path = []

    if type(desired) != type(actual):
        return (
            f"{format_path(path)} type differs: "
            f"desired={type(desired).__name__} actual={type(actual).__name__}"
        )

    if isinstance(desired, dict):
        desired_keys = set(desired.keys())
        actual_keys = set(actual.keys())

        for key in sorted(desired_keys - actual_keys):
            return f"{format_path(path + [str(key)])} missing in actual"

        for key in sorted(actual_keys - desired_keys):
            return f"{format_path(path + [str(key)])} present only in actual"

        for key in sorted(desired_keys):
            diff = first_diff(desired[key], actual[key], path + [str(key)])
            if diff:
                return diff
        return None

    if isinstance(desired, list):
        if len(desired) != len(actual):
            return f"{format_path(path)} list length differs: desired={len(desired)} actual={len(actual)}"

        for idx, (d_item, a_item) in enumerate(zip(desired, actual)):
            diff = first_diff(d_item, a_item, path + [f"[{idx}]"])
            if diff:
                return diff
        return None

    if desired != actual:
        return (
            f"{format_path(path)} differs: "
            f"desired={short_repr(desired)} actual={short_repr(actual)}"
        )

    return None


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