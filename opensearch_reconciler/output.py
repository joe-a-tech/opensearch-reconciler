from __future__ import annotations

from typing import List

from .models import Action

try:
    from rich.console import Console
    from rich.table import Table

    RICH_AVAILABLE = True
    CONSOLE = Console()
except Exception:
    RICH_AVAILABLE = False
    Console = None
    Table = None
    CONSOLE = None


def print_plan(actions: List[Action], show_noop: bool = False) -> None:
    rows = [a for a in actions if show_noop or a.action != "noop"]

    if RICH_AVAILABLE and CONSOLE is not None:
        table = Table(title="OpenSearch Reconcile Plan")
        table.add_column("Action", no_wrap=True)
        table.add_column("Kind", no_wrap=True)
        table.add_column("Customer", no_wrap=True)
        table.add_column("Name", no_wrap=True)
        table.add_column("Details")

        for action in rows:
            style = {
                "create": "green",
                "update": "yellow",
                "delete": "red",
                "noop": "dim",
            }.get(action.action, "white")
            table.add_row(
                action.action.upper(),
                action.kind,
                action.customer,
                action.name,
                action.details,
                style=style,
            )

        CONSOLE.print(table)
        return

    header = f"{'ACTION':<20} {'KIND':<20} {'CUSTOMER':<15} {'NAME':<30} DETAILS"
    print(header)
    print("-" * len(header))
    for action in rows:
        print(f"{action.action.upper():<20} {action.kind:<20} {action.customer:<15} {action.name:<30} {action.details}")