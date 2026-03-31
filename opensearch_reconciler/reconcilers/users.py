from __future__ import annotations

from typing import Dict

from ..utils import comparable, strip_reconciler_marker
from .security_base import SecurityObjectReconciler


class UserReconciler(SecurityObjectReconciler):
    kind = "users"
    resource_name = "internalusers"

    def normalise_for_compare(self, data: Dict[str, object]) -> Dict[str, object]:
        data = strip_reconciler_marker(data)
        for key in (
            "hash",
            "password",
            "password_hash",
            "opendistro_security_roles",
            "security_roles",
        ):
            data.pop(key, None)
        return comparable(data)