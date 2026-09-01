from __future__ import annotations

import argparse
import json
import os
import sys

from app.coverage_reconciliation import ReconciliationConfig
from app.coverage_reconciliation_runs import (
    CoverageReconciliationStore,
    public_reconciliation_status,
)
from app.event_dates import parse_calendar_date


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic bulk RA/Scenegraph reconciliation.")
    subparsers = parser.add_subparsers(dest="command")
    status = subparsers.add_parser("status", help="Display persisted reconciliation state without mutations.")
    selection = status.add_mutually_exclusive_group(required=True)
    selection.add_argument("--latest", action="store_true")
    selection.add_argument("--run-id", type=int)
    status.add_argument("--verbose", action="store_true")

    parser.add_argument("--min-date")
    parser.add_argument("--max-date")
    parser.add_argument("--background", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL must be set")
    store = CoverageReconciliationStore(database_url)
    if args.command == "status":
        run = store.get_latest() if args.latest else store.get_run(args.run_id)
        print(json.dumps(public_reconciliation_status(run, verbose=args.verbose), indent=2))
        return 0

    if not args.min_date or not args.max_date:
        raise SystemExit("--min-date and --max-date are required")
    if not args.background:
        raise SystemExit("Reconciliation must be launched with --background")
    min_date = parse_calendar_date(args.min_date)
    requested_max = args.max_date
    if requested_max != "auto":
        max_date = parse_calendar_date(requested_max)
        if min_date > max_date:
            raise SystemExit("--min-date cannot be later than --max-date")
    config = ReconciliationConfig.from_env()
    run = store.enqueue(
        min_date=min_date,
        requested_max_date=requested_max,
        future_horizon_days=config.max_future_days,
        audit_chunk_days=config.audit_chunk_days,
        pipeline_chunk_days=config.pipeline_chunk_days,
        max_attempts=config.max_attempts,
        source_quarantine_ttl_days=config.source_quarantine_ttl_days,
    )
    print(
        json.dumps(
            {
                "run_id": int(run["id"]),
                "status": str(run["status"]),
                "requested": f"{min_date.isoformat()}..{requested_max}",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
