from __future__ import annotations

import os
from datetime import date

import psycopg

from app.coverage_reconciliation_runs import CoverageReconciliationStore


MIN_DATE = date(2099, 2, 1)
MAX_DATE = date(2099, 2, 3)


def cleanup(database_url: str) -> None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM coverage_reconciliations WHERE requested_min_date = %s",
                (MIN_DATE,),
            )
        connection.commit()


def test_reconciliation_store_persists_dates_and_requeues_failed_range():
    database_url = os.environ["DATABASE_URL"]
    store = CoverageReconciliationStore(database_url)
    cleanup(database_url)
    try:
        first = store.enqueue(
            min_date=MIN_DATE,
            requested_max_date=MAX_DATE.isoformat(),
            future_horizon_days=365,
            audit_chunk_days=31,
            pipeline_chunk_days=7,
            max_attempts=3,
            source_quarantine_ttl_days=11,
        )
        run_id = int(first["id"])
        store.update_run(run_id, resolved_max_date=MAX_DATE, status="running")
        store.initialize_dates(run_id, MIN_DATE, MAX_DATE, today=MAX_DATE)
        store.update_date(
            run_id,
            MIN_DATE.isoformat(),
            status="processing",
            initial_audit_status="missing_events",
            initial_missing_count=1,
            initial_audit={"date": MIN_DATE.isoformat(), "missing_count": 1},
            pipeline_status="running",
            pipeline_attempt_count=1,
        )
        store.update_run(run_id, status="failed", error="interrupted", completed=True)

        resumed = store.enqueue(
            min_date=MIN_DATE,
            requested_max_date=MAX_DATE.isoformat(),
            future_horizon_days=365,
            audit_chunk_days=31,
            pipeline_chunk_days=7,
            max_attempts=3,
            source_quarantine_ttl_days=3,
        )
        persisted = store.get_run(run_id)

        assert int(resumed["id"]) == run_id
        assert resumed["status"] == "queued"
        assert resumed["source_quarantine_ttl_days"] == 11
        assert persisted["source_quarantine_ttl_days"] == 11
        assert len(persisted["dates"]) == 3
        assert persisted["dates"][0]["initial_audit"]["missing_count"] == 1
        assert persisted["dates"][0]["pipeline_attempt_count"] == 1
    finally:
        cleanup(database_url)


def test_reconciliation_worker_advisory_lock_is_single_owner_and_releasable():
    database_url = os.environ["DATABASE_URL"]
    first = CoverageReconciliationStore(database_url)
    second = CoverageReconciliationStore(database_url)

    first_lock = first.acquire_worker_lock()
    assert first_lock is not None
    try:
        assert second.acquire_worker_lock() is None
    finally:
        first.release_worker_lock(first_lock)

    released = second.acquire_worker_lock()
    assert released is not None
    second.release_worker_lock(released)
