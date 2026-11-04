"""One finite, local-only snapshot backfill; run IDs remain in PostgreSQL."""

from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlparse

import psycopg

from app.event_tag_extraction import EventTagExtractionConfig
from app.promoter_role_backfill import MAX_EVENTS, create_run, extraction_config_hash, process_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create and process the local snapshot")
    args = parser.parse_args()
    url = os.environ["DATABASE_URL"]
    if urlparse(url).hostname != "db":
        raise SystemExit("local Compose database host 'db' is required")
    with psycopg.connect(url) as connection:
        event_ids = [int(row[0]) for row in connection.execute("SELECT id FROM events ORDER BY id")]
        print(json.dumps({"snapshot_events": len(event_ids), "max_batch_size": MAX_EVENTS}), flush=True)
        if not args.apply or not event_ids:
            return 0
        config = extraction_config_hash(EventTagExtractionConfig.from_env())
        run_ids = [create_run(connection, tuple(event_ids[i:i + MAX_EVENTS]), config)
                   for i in range(0, len(event_ids), MAX_EVENTS)]
        connection.commit()
        print(json.dumps({"created_runs": run_ids}), flush=True)
        has_failures = False
        for run_id in run_ids:
            status = process_run(connection, run_id, config)
            print(json.dumps({"run_id": run_id, "status": status}), flush=True)
            if status == "paused":
                return 1
            if status == "failed":
                failures = connection.execute("SELECT error_code FROM promoter_role_backfill_item WHERE run_id = %s AND status = 'failed'", (run_id,)).fetchall()
                connection.commit()
                if any(code in {"provider_system_failure", "system_failure"} for (code,) in failures):
                    return 1
                status = process_run(connection, run_id, config, retry_failed=True)
                print(json.dumps({"run_id": run_id, "retry_status": status}), flush=True)
                if status == "paused":
                    return 1
                if status == "failed":
                    failures = connection.execute("SELECT error_code FROM promoter_role_backfill_item WHERE run_id = %s AND status = 'failed'", (run_id,)).fetchall()
                    connection.commit()
                    if any(code in {"provider_system_failure", "system_failure"} for (code,) in failures):
                        return 1
                has_failures = has_failures or status == "failed"
        return 1 if has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
