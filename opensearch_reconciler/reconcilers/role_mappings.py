from __future__ import annotations

from .security_base import SecurityObjectReconciler


class RoleMappingReconciler(SecurityObjectReconciler):
    kind = "role_mappings"
    resource_name = "rolesmapping"