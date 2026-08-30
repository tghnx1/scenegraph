from __future__ import annotations

import os
import socket
import time

from app.coverage_repair import CoverageRepairOrchestrator
from app.coverage_runs import CoverageRunStore


def process_next_run(
    store: CoverageRunStore,
    *,
    worker_id: str,
    orchestrator_factory=CoverageRepairOrchestrator,
) -> bool:
    run = store.claim_next(worker_id)
    if run is None:
        return False
    run_id = int(run["id"])
    print(
        f"[coverage-worker] run={run_id} range={run['min_date']}..{run['max_date']} status=started",
        flush=True,
    )
    result = orchestrator_factory(store).run(run_id)
    print(
        f"[coverage-worker] run={run_id} status={result['status']} "
        f"total_missing={result['total_missing']}",
        flush=True,
    )
    return True


def run_forever(
    store: CoverageRunStore,
    *,
    worker_id: str,
    poll_seconds: float,
    sleep=time.sleep,
) -> None:
    while True:
        worker_lock = store.acquire_worker_lock()
        if worker_lock is None:
            sleep(poll_seconds)
            continue
        try:
            while True:
                if not process_next_run(store, worker_id=worker_id):
                    sleep(poll_seconds)
        finally:
            store.release_worker_lock(worker_lock)


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set")
    poll_seconds = float(os.environ.get("COVERAGE_WORKER_POLL_SECONDS", "5"))
    if poll_seconds <= 0:
        raise ValueError("COVERAGE_WORKER_POLL_SECONDS must be positive")
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    run_forever(
        CoverageRunStore(database_url),
        worker_id=worker_id,
        poll_seconds=poll_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
