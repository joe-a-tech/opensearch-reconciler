from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .api import OpenSearchAPI
from .models import Action, ManagedObject
from .reconcilers import RECONCILERS
from .utils import ReconcileError

LOG = logging.getLogger("opensearch_reconciler")


def infer_customer_from_actual(kind: str, actual_name: str, actual_body: dict) -> str:
    meta = actual_body.get("_reconciler", {})
    if isinstance(meta, dict) and isinstance(meta.get("customer"), str):
        return meta["customer"]
    return "unknown"


def build_plan(
    api: OpenSearchAPI,
    desired_state: Dict[str, Dict[str, ManagedObject]],
    customer_filter: Optional[str] = None,
    show_diff: bool = False,
) -> List[Action]:
    actions: List[Action] = []

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

    for action in actions:
        if action.action == "noop":
            continue

        reconciler = RECONCILERS[action.kind]

        if action.action == "create":
            obj = desired_by_kind_name[(action.kind, action.name)]
            LOG.info("Creating %s %s", action.kind, action.name)
            reconciler.create(api, obj)
        elif action.action == "update":
            obj = desired_by_kind_name[(action.kind, action.name)]
            LOG.info("Updating %s %s", action.kind, action.name)
            reconciler.update(api, obj)
        elif action.action == "delete":
            if not confirm_deletes:
                LOG.warning("Skipping delete for %s %s (use --confirm-deletes)", action.kind, action.name)
                continue
            LOG.info("Deleting %s %s", action.kind, action.name)
            reconciler.delete(api, action.name)
        else:
            raise ReconcileError(f"Unknown action: {action.action}")