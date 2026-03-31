from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from .api import OpenSearchAPI
from .loader import load_desired_state
from .output import print_plan
from .plan import apply_plan, build_plan

LOG = logging.getLogger("opensearch_reconciler")


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def env_default(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def parse_verify(value: str) -> bool | Path:
    lowered = value.strip().lower()
    if lowered in {"true", "yes", "1"}:
        return True
    if lowered in {"false", "no", "0"}:
        return False
    return Path(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenSearch reconciler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--definitions-dir", default=env_default("OS_RECONCILE_DEFINITIONS_DIR", "./definitions"))
    common.add_argument(
        "--base-url",
        default=env_default("OS_RECONCILE_BASE_URL"),
        required=env_default("OS_RECONCILE_BASE_URL") is None,
    )
    common.add_argument("--username", default=env_default("OS_RECONCILE_USERNAME"))
    common.add_argument("--password", default=env_default("OS_RECONCILE_PASSWORD"))
    common.add_argument("--verify", default=env_default("OS_RECONCILE_VERIFY", "true"))
    common.add_argument("--client-cert", default=env_default("OS_RECONCILE_CLIENT_CERT"))
    common.add_argument("--client-key", default=env_default("OS_RECONCILE_CLIENT_KEY"))
    common.add_argument("--timeout", type=int, default=int(env_default("OS_RECONCILE_TIMEOUT", "30")))
    common.add_argument("--customer", help="Only reconcile a single customer")
    common.add_argument("--show-noop", action="store_true")
    common.add_argument("--show-diff", action="store_true")
    common.add_argument("--verbose", action="store_true")

    subparsers.add_parser("plan", parents=[common], help="Show planned actions")

    apply = subparsers.add_parser("apply", parents=[common], help="Apply planned actions")
    apply.add_argument("--confirm-deletes", action="store_true")

    lst = subparsers.add_parser("list", parents=[common], help="List plan including noops")
    lst.set_defaults(show_noop=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.verbose)

    LOG.info("Command=%s", args.command)
    if args.customer:
        LOG.info("Customer filter=%s", args.customer)

    try:
        definitions_dir = Path(args.definitions_dir)
        verify = parse_verify(args.verify)
        client_cert = Path(args.client_cert) if args.client_cert else None
        client_key = Path(args.client_key) if args.client_key else None

        desired_state = load_desired_state(definitions_dir)
        api = OpenSearchAPI(
            base_url=args.base_url,
            username=args.username,
            password=args.password,
            verify=verify,
            client_cert=client_cert,
            client_key=client_key,
            timeout=args.timeout,
        )

        actions = build_plan(
            api=api,
            desired_state=desired_state,
            customer_filter=args.customer,
            show_diff=args.show_diff,
        )
        print_plan(actions, show_noop=args.show_noop)

        if args.command == "apply":
            apply_plan(
                api=api,
                desired_state=desired_state,
                actions=actions,
                confirm_deletes=args.confirm_deletes,
            )
            LOG.info("Apply complete")
        else:
            LOG.info("Plan complete")

        return 0
    except Exception as exc:
        LOG.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())