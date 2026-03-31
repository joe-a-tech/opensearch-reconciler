from __future__ import annotations

from .security_base import SecurityObjectReconciler


class RoleReconciler(SecurityObjectReconciler):
    kind = "roles"
    resource_name = "roles"