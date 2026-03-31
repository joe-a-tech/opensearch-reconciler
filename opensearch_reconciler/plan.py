from __future__ import annotations

import logging
from collections import Counter
from typing import Dict, List, Optional, Tuple

from .api import OpenSearchAPI
from .models import Action, ManagedObject
from .reconcilers import RECONCILERS
from .utils import ReconcileError

LOG = logging.getLogger("opensearch_reconciler")


def infer_customer_from_actual(kind: str, actual_name: str, actual_body: dict) -> str:
    if kind == "tenant":
        return actual_name

    if kind in {"index_templates", "component_templates", "ingest_pipelines"}:
        meta = actual_body.get("_meta", {})
        if isinstance(meta, dict) and isinstance(meta.get("customer"), str):
            return meta["customer"]
        return "unknown"

    if kind == "ism_policies":
        if "policy" in actual_body and isinstance(actual_body["policy"], dict):
            actual_body = actual_body["policy"]
        desc = actual_body.get("description", "")
        if isinstance(desc, str) and "[managed customer=" in desc:
            marker = desc.split("[managed customer=", 1)[1].split("]", 1)[0]
            return marker.strip() or "unknown"
        return "unknown"

    meta = actual_body.get("_reconciler", {})
    if isinstance(meta, dict) and isinstance(meta.get("customer"), str):
        return meta["customer"]

    return "unknown"


def log_plan_summary(actions: List[Action]) -> None:
    counts = Counter(action.action for action in actions)
    LOG.info(
        "Plan summary: create=%d update=%d delete=%d noop=%d total=%d",
        counts.get("create", 0),
        counts.get("update", 0),
        counts.get("delete", 0),
        counts.get("noop", 0),
        len(actions),
    )


def build_plan(
    api: OpenSearchAPI,
    desired_state: Dict[str, Dict[str, ManagedObject]],
    customer_filter: Optional[str] = None,
    show_diff: bool = False,
) -> List[Action]:
    actions: List[Action] = []

    LOG.info(
        "Building plan%s",
        f" for customer={customer_filter}" if customer_filter else "",
    )

    for kind, reconciler in RECONCILERS.items():
        desired = desired_state.get(kind, {})
        actual = reconciler.list_actual(api)

        desired_names: set[str] = set()

        for _, obj in sorted(desired.items(), key=lambda kv: (kv[1].customer, kv[1].name)):
            if customer_filter and obj.customer != customer_filter:
                continue

            desired_names.add(obj.name)
            actual_body = reconciler.get_actual(api, obj)

            if actual_body is None:
                actions.append(Action(kind, obj.name, obj.customer, "create", str(obj.source_file)))
                continue

            if reconciler.objects_differ(obj.body, actual_body):
                actions.append(
                    Action(
                        kind,
                        obj.name,
                        obj.customer,
                        "update",
                        reconciler.diff_summary(obj.body, actual_body, show_diff=show_diff),
                    )
                )
            else:
                actions.append(Action(kind, obj.name, obj.customer, "noop", ""))

        for actual_name, actual_body in sorted(actual.items()):
            if actual_name in desired_names:
                continue
            if not reconciler.is_managed(actual_body):
                continue

            actual_customer = infer_customer_from_actual(kind, actual_name, actual_body)
            if customer_filter and actual_customer != customer_filter:
                continue

            actions.append(
                Action(
                    kind,
                    actual_name,
                    actual_customer,
                    "delete",
                    "managed object not present in definitions",
                )
            )

    action_order = {"create": 0, "update": 1, "delete": 2, "noop": 3}
    actions.sort(key=lambda a: (action_order.get(a.action, 99), a.kind, a.customer, a.name))

    log_plan_summary(actions)
    return actions


def apply_plan(
    api: OpenSearchAPI,
    desired_state: Dict[str, Dict[str, ManagedObject]],
    actions: List[Action],
    confirm_deletes: bool,
) -> None:
    desired_by_kind_name: Dict[Tuple[str, str], ManagedObject] = {}
    for kind, items in desired_state.items():
        for _, obj in items.items():
            desired_by_kind_name[(kind, obj.name)] = obj

    counts = Counter()
    LOG.info("Starting apply")

    for action in actions:
        if action.action == "noop":
            counts["noop"] += 1
            continue

        reconciler = RECONCILERS[action.kind]

        if action.action == "create":
            obj = desired_by_kind_name[(action.kind, action.name)]
            LOG.info("Applying action=create kind=%s customer=%s name=%s", action.kind, obj.customer, obj.name)
            reconciler.create(api, obj)
            counts["create"] += 1

        elif action.action == "update":
            obj = desired_by_kind_name[(action.kind, action.name)]
            LOG.info("Applying action=update kind=%s customer=%s name=%s", action.kind, obj.customer, obj.name)
            reconciler.update(api, obj)
            counts["update"] += 1

        elif action.action == "delete":
            if not confirm_deletes:
                LOG.warning(
                    "Skipping action=delete kind=%s customer=%s name=%s reason=--confirm-deletes not set",
                    action.kind,
                    action.customer,
                    action.name,
                )
                counts["delete_skipped"] += 1
                continue

            LOG.info("Applying action=delete kind=%s customer=%s name=%s", action.kind, action.customer, action.name)
            reconciler.delete(api, action.name)
            counts["delete"] += 1

        else:
            raise ReconcileError(f"Unknown action: {action.action}")

    LOG.info(
        "Apply summary: create=%d update=%d delete=%d delete_skipped=%d noop=%d",
        counts.get("create", 0),
        counts.get("update", 0),
        counts.get("delete", 0),
        counts.get("delete_skipped", 0),
        counts.get("noop", 0),
    )