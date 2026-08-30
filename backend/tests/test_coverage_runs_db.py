from __future__ import annotations

import os
from datetime import date

import psycopg

from app.coverage_runs import CoverageRunStore


MIN_DATE = date(2099, 1, 2)
MAX_DATE = date(2099, 1, 3)


def cleanup(database_url: str) -> None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM coverage_runs WHERE min_date = %s AND max_date = %s",
                (MIN_DATE, MAX_DATE),
            )
        connection.commit()


def test_coverage_run_store_persists_dates_and_deduplicates_active_range():
    database_url = os.environ["DATABASE_URL"]
    store = CoverageRunStore(database_url)
    cleanup(database_url)
    try:
        first = store.enqueue(min_date=MIN_DATE, max_date=MAX_DATE, max_attempts=2)
        duplicate = store.enqueue(min_date=MIN_DATE, max_date=MAX_DATE, max_attempts=3)

        assert duplicate["id"] == first["id"]
        run_id = int(first["id"])
        store.update_run(run_id, status="running")
        store.update_date(
            run_id,
            MIN_DATE.isoformat(),
            status="repairing",
            audit_status="missing_events",
            initial_missing_count=1,
            initial_audit={"date": MIN_DATE.isoformat(), "missing_count": 1},
            backfill_status="running",
            backfill_attempt_count=1,
            started=True,
        )

        persisted = store.get_run(run_id)

        assert persisted["status"] == "running"
        assert len(persisted["dates"]) == 2
        assert persisted["dates"][0]["initial_audit"]["missing_count"] == 1
        assert persisted["dates"][0]["backfill_attempt_count"] == 1
    finally:
        cleanup(database_url)


def test_coverage_worker_advisory_lock_is_single_owner_and_releasable():
    database_url = os.environ["DATABASE_URL"]
    first_store = CoverageRunStore(database_url)
    second_store = CoverageRunStore(database_url)

    first_lock = first_store.acquire_worker_lock()
    assert first_lock is not None
    try:
        assert second_store.acquire_worker_lock() is None
    finally:
        first_store.release_worker_lock(first_lock)

    released_lock = second_store.acquire_worker_lock()
    assert released_lock is not None
    second_store.release_worker_lock(released_lock)
