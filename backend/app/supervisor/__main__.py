from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .state import DeterministicSupervisor, JsonStateStore, ProductRunReader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read Scenegraph ingestion supervisor state.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    status = subparsers.add_parser("status")
    status.add_argument("--latest", action="store_true", help="Show the latest persisted import run.")
    details = subparsers.add_parser("details")
    details.add_argument("--run-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL must be set")
    state_path = os.environ.get(
        "SUPERVISOR_STATE_PATH",
        str(Path(__file__).resolve().parents[2] / "data/supervisor/state.json"),
    )
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        supervisor = DeterministicSupervisor(
            ProductRunReader(connection),
            JsonStateStore(Path(state_path)),
            telegram=_NoopTelegram(),
        )
        report = supervisor.observe(None if args.command == "status" else args.run_id)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


class _NoopTelegram:
    def send(self, _message: str) -> None:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
