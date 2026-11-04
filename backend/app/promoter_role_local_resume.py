"""Resume a finite list of local backfill runs, waiting after provider quota errors."""

from __future__ import annotations

import argparse
import json
import os
import time
from urllib.parse import urlparse

import psycopg

from app.event_tag_extraction import EventTagExtractionConfig
from app.promoter_role_backfill import extraction_config_hash, process_run

QUOTA_WAIT_SECONDS = 6 * 60 * 60


def wait_for_quota(connection: psycopg.Connection, run_id: int) -> bool:
    row = connection.execute("""
        SELECT GREATEST(0, EXTRACT(EPOCH FROM (updated_at + make_interval(secs => %s) - now())))
        FROM promoter_role_backfill_item
        WHERE run_id = %s AND status = 'pending' AND error_code = 'provider_quota'
        ORDER BY updated_at DESC LIMIT 1
    """, (QUOTA_WAIT_SECONDS, run_id)).fetchone()
    connection.commit()
    if row is None:
        return False
    seconds = float(row[0])
    print(json.dumps({"run_id": run_id, "status": "waiting_for_quota", "wait_seconds": round(seconds)}), flush=True)
    if seconds > 0:
        time.sleep(seconds)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=int, action="append", required=True)
    args = parser.parse_args()
    if len(set(args.run_id)) != len(args.run_id):
        parser.error("run IDs must be unique")
    url = os.environ["DATABASE_URL"]
    if urlparse(url).hostname != "db":
        raise SystemExit("local Compose database host 'db' is required")
    config = extraction_config_hash(EventTagExtractionConfig.from_env())
    with psycopg.connect(url) as connection:
        has_failures = False
        for run_id in args.run_id:
            row = connection.execute("SELECT status FROM promoter_role_backfill_run WHERE id = %s", (run_id,)).fetchone()
            connection.commit()
            if row is None:
                raise SystemExit(f"run {run_id} not found")
            if row[0] == "succeeded":
                continue
            if row[0] == "paused" and not wait_for_quota(connection, run_id):
                print(json.dumps({"run_id": run_id, "status": "paused_non_quota"}), flush=True)
                return 1
            while True:
                status = process_run(connection, run_id, config, retry_failed=True)
                print(json.dumps({"run_id": run_id, "status": status}), flush=True)
                if status != "paused":
                    break
                if not wait_for_quota(connection, run_id):
                    return 1
            if status == "failed":
                failures = connection.execute("SELECT error_code FROM promoter_role_backfill_item WHERE run_id = %s AND status = 'failed'", (run_id,)).fetchall()
                connection.commit()
                if any(code in {"provider_system_failure", "system_failure"} for (code,) in failures):
                    return 1
                has_failures = True
        return 1 if has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
