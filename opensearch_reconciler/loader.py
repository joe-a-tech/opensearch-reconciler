from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from .models import ManagedObject
from .utils import ReconcileError, annotate_managed


def load_yaml_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ReconcileError(f"YAML must contain an object at top level: {path}")
    return data


def add_desired_object(
    desired: Dict[str, Dict[str, ManagedObject]],
    name_registry: Dict[str, Dict[str, Path]],
    obj: ManagedObject,
    key: str,
) -> None:
    prior = name_registry.setdefault(obj.kind, {}).get(obj.name)
    if prior is not None:
        raise ReconcileError(
            f"Duplicate {obj.kind} name '{obj.name}' across customers: "
            f"{prior} and {obj.source_file}"
        )

    name_registry[obj.kind][obj.name] = obj.source_file
    desired[obj.kind][key] = obj


def load_desired_state(definitions_dir: Path) -> Dict[str, Dict[str, ManagedObject]]:
    if not definitions_dir.exists() or not definitions_dir.is_dir():
        raise ReconcileError(f"Definitions dir does not exist or is not a directory: {definitions_dir}")

    desired: Dict[str, Dict[str, ManagedObject]] = {
        "tenant": {},
        "roles": {},
        "role_mappings": {},
        "users": {},
        "index_templates": {},
        "component_templates": {},
        "ingest_pipelines": {},
        "ism_policies": {},
    }
    name_registry: Dict[str, Dict[str, Path]] = {kind: {} for kind in desired}

    customer_dirs = [p for p in sorted(definitions_dir.iterdir()) if p.is_dir()]
    if not customer_dirs:
        raise ReconcileError(f"No customer directories found under {definitions_dir}")

    for customer_dir in customer_dirs:
        customer = customer_dir.name

        tenant_file = customer_dir / "tenant.yaml"
        if tenant_file.exists():
            tenant_body = annotate_managed(load_yaml_file(tenant_file), customer, "tenant", customer)
            tenant_obj = ManagedObject(customer, "tenant", customer, tenant_body, tenant_file)
            add_desired_object(desired, name_registry, tenant_obj, customer)

        for subdir_name in (
            "roles",
            "role_mappings",
            "users",
            "index_templates",
            "component_templates",
            "ingest_pipelines",
            "ism_policies",
        ):
            subdir = customer_dir / subdir_name
            if not subdir.exists():
                continue
            if not subdir.is_dir():
                raise ReconcileError(f"Expected directory: {subdir}")

            for file_path in sorted(subdir.glob("*.y*ml")):
                name = file_path.stem
                body = annotate_managed(load_yaml_file(file_path), customer, subdir_name, name)
                obj = ManagedObject(customer, subdir_name, name, body, file_path)
                add_desired_object(desired, name_registry, obj, f"{customer}/{name}")

    return desired