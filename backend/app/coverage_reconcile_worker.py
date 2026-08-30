from __future__ import annotations

import os
import socket
import time
from collections.abc import Callable

from app.coverage_reconciliation import CoverageReconciliationOrchestrator
from app.coverage_reconciliation_runs import CoverageReconciliationStore


def process_next_reconciliation(
    store: CoverageReconciliationStore,
    *,
    worker_id: str,
    orchestrator_factory: Callable[..., CoverageReconciliationOrchestrator] = CoverageReconciliationOrchestrator,
) -> bool:
    run = store.claim_next(worker_id)
    if run is None:
        return False
    run_id = int(run["id"])
    print(
        f"[coverage-reconcile-worker] run={run_id} "
        f"requested={run['requested_min_date']}..{run['requested_max_date']} status=started",
        flush=True,
    )
    try:
        result = orchestrator_factory(store).run(run_id)
    except Exception as exc:
        print(
            f"[coverage-reconcile-worker] run={run_id} status=failed error_type={type(exc).__name__}",
            flush=True,
        )
        return True
    print(
        f"[coverage-reconcile-worker] run={run_id} status={result['status']} "
        f"final_missing={result['final_missing']}",
        flush=True,
    )
    return True


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL must be set")
    poll_seconds = max(1.0, float(os.environ.get("RECONCILIATION_WORKER_POLL_SECONDS", "5")))
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    store = CoverageReconciliationStore(database_url)
    while True:
        lock = store.acquire_worker_lock()
        if lock is None:
            time.sleep(poll_seconds)
            continue
        try:
            processed = process_next_reconciliation(store, worker_id=worker_id)
        finally:
            store.release_worker_lock(lock)
        if not processed:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
