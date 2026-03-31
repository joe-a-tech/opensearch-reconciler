from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class ManagedObject:
    customer: str
    kind: str
    name: str
    body: Dict[str, Any]
    source_file: Path


@dataclass(frozen=True)
class Action:
    kind: str
    name: str
    customer: str
    action: str  # create | update | delete | noop
    details: str = ""