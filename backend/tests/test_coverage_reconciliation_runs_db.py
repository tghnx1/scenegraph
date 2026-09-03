from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.coverage_reconciliation_runs import CoverageReconciliationStore


MIN_DATE = date(2099, 2, 1)
MAX_DATE = date(2099, 2, 3)


class FakeCursor:
    def __init__(self, database: "FakeDatabase") -> None:
        self.database = database
        self.rows: list[dict[str, object]] = []

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> None:
        params = params or ()
        normalized = " ".join(sql.split())
        if "SELECT pg_advisory_xact_lock" in normalized:
            return
        if "SELECT pg_try_advisory_lock" in normalized:
            acquired = not self.database.lock_acquired
            if acquired:
                self.database.lock_acquired = True
            self.rows = [{"acquired": acquired}]
            return
        if "SELECT pg_advisory_unlock" in normalized:
            self.database.lock_acquired = False
            self.rows = [{"pg_advisory_unlock": True}]
            return
        if (
            "SELECT * FROM coverage_reconciliations" in normalized
            and "requested_min_date = %s" in normalized
        ):
            min_date, requested_max_date, refresh_all_future = params
            matches = [
                row
                for row in self.database.runs
                if row["requested_min_date"] == min_date
                and row["requested_max_date"] == requested_max_date
                and row["refresh_all_future"] == refresh_all_future
                and row["status"] in {"queued", "running", "failed"}
            ]
            matches.sort(key=lambda row: int(row["id"]), reverse=True)
            self.rows = [matches[0].copy()] if matches else []
            return
        if normalized.startswith("UPDATE coverage_reconciliations SET") and "RETURNING *" in normalized:
            run_id = int(params[-1])
            row = self.database.run_by_id(run_id)
            row.update(
                {
                    "status": "queued",
                    "error": None,
                    "completed_at": None,
                    "worker_id": None,
                    "updated_at": self._now(),
                }
            )
            self.rows = [row.copy()]
            return
        if normalized.startswith("INSERT INTO coverage_reconciliations"):
            (
                min_date,
                requested_max_date,
                future_horizon_days,
                audit_chunk_days,
                pipeline_chunk_days,
                max_attempts,
                source_quarantine_ttl_days,
                refresh_all_future,
            ) = params
            row = {
                "id": self.database.next_run_id,
                "requested_min_date": min_date,
                "requested_max_date": requested_max_date,
                "resolved_max_date": None,
                "future_horizon_days": future_horizon_days,
                "audit_chunk_days": audit_chunk_days,
                "pipeline_chunk_days": pipeline_chunk_days,
                "max_attempts": max_attempts,
                "source_quarantine_ttl_days": source_quarantine_ttl_days,
                "refresh_all_future": refresh_all_future,
                "status": "queued",
                "phase": "pending",
                "current_min_date": None,
                "current_max_date": None,
                "initial_missing": None,
                "final_missing": None,
                "worker_id": None,
                "error": None,
                "started_at": None,
                "completed_at": None,
                "created_at": self._now(),
                "updated_at": self._now(),
            }
            self.database.next_run_id += 1
            self.database.runs.append(row)
            self.rows = [row.copy()]
            return
        if normalized.startswith("SELECT r.* FROM coverage_reconciliations r WHERE r.id = %s"):
            run_id = int(params[0])
            row = self.database.run_by_id(run_id)
            self.rows = [row.copy()]
            return
        if normalized.startswith("SELECT r.* FROM coverage_reconciliations r ORDER BY r.id DESC LIMIT 1"):
            row = self.database.runs[-1]
            self.rows = [row.copy()]
            return
        if normalized.startswith("SELECT * FROM coverage_reconciliation_dates"):
            run_id = int(params[0])
            self.rows = [
                row.copy()
                for row in sorted(
                    self.database.date_rows_for(run_id),
                    key=lambda item: item["coverage_date"],
                )
            ]
            return
        raise AssertionError(f"Unhandled SQL: {sql}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows = self.rows
        self.rows = []
        return rows

    def executemany(self, sql: str, seq) -> None:
        normalized = " ".join(sql.split())
        if not normalized.startswith("INSERT INTO coverage_reconciliation_dates"):
            raise AssertionError(f"Unhandled SQL: {sql}")
        for run_id, coverage_date, period in seq:
            self.database.date_rows.append(
                {
                    "reconciliation_id": run_id,
                    "coverage_date": coverage_date,
                    "period": period,
                    "status": "pending",
                    "initial_audit_status": None,
                    "initial_missing_count": None,
                    "pipeline_status": "pending",
                    "pipeline_attempt_count": 0,
                    "final_audit_status": None,
                    "final_missing_count": None,
                    "initial_audit": None,
                    "final_audit": None,
                    "error": None,
                    "started_at": None,
                    "completed_at": None,
                    "updated_at": self._now(),
                }
            )


class FakeConnection:
    def __init__(self, database: "FakeDatabase") -> None:
        self.database = database

    def cursor(self):
        return FakeCursor(self.database)

    def commit(self) -> None:
        return None

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeDatabase:
    def __init__(self) -> None:
        self.runs: list[dict[str, object]] = []
        self.date_rows: list[dict[str, object]] = []
        self.next_run_id = 1
        self.lock_acquired = False

    def run_by_id(self, run_id: int) -> dict[str, object]:
        for row in self.runs:
            if int(row["id"]) == run_id:
                return row
        raise LookupError(f"run {run_id} not found")

    def date_rows_for(self, run_id: int) -> list[dict[str, object]]:
        return [row for row in self.date_rows if int(row["reconciliation_id"]) == run_id]


def make_store() -> tuple[CoverageReconciliationStore, FakeDatabase]:
    database = FakeDatabase()
    store = CoverageReconciliationStore("postgresql://test/scenegraph")
    store._connect = lambda **_kwargs: FakeConnection(database)  # type: ignore[method-assign]
    return store, database


def seed_run(
    database: FakeDatabase,
    *,
    refresh_all_future: bool,
    status: str = "failed",
) -> dict[str, object]:
    run = {
        "id": database.next_run_id,
        "requested_min_date": MIN_DATE,
        "requested_max_date": MAX_DATE.isoformat(),
        "resolved_max_date": MAX_DATE,
        "future_horizon_days": 365,
        "audit_chunk_days": 31,
        "pipeline_chunk_days": 7,
        "max_attempts": 3,
        "source_quarantine_ttl_days": 11,
        "refresh_all_future": refresh_all_future,
        "status": status,
        "phase": "pending",
        "current_min_date": None,
        "current_max_date": None,
        "initial_missing": None,
        "final_missing": None,
        "worker_id": None,
        "error": "interrupted" if status == "failed" else None,
        "started_at": datetime.now(timezone.utc),
        "completed_at": datetime.now(timezone.utc) if status == "failed" else None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    database.next_run_id += 1
    database.runs.append(run)
    database.date_rows.extend(
        [
            {
                "reconciliation_id": run["id"],
                "coverage_date": MIN_DATE,
                "period": "historical",
                "status": "processing",
                "initial_audit_status": "missing_events",
                "initial_missing_count": 1,
                "pipeline_status": "running",
                "pipeline_attempt_count": 1,
                "final_audit_status": None,
                "final_missing_count": None,
                "initial_audit": {"date": MIN_DATE.isoformat(), "missing_count": 1},
                "final_audit": None,
                "error": None,
                "started_at": datetime.now(timezone.utc),
                "completed_at": None,
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "reconciliation_id": run["id"],
                "coverage_date": date(2099, 2, 2),
                "period": "future",
                "status": "pending",
                "initial_audit_status": None,
                "initial_missing_count": None,
                "pipeline_status": "pending",
                "pipeline_attempt_count": 0,
                "final_audit_status": None,
                "final_missing_count": None,
                "initial_audit": None,
                "final_audit": None,
                "error": None,
                "started_at": None,
                "completed_at": None,
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "reconciliation_id": run["id"],
                "coverage_date": MAX_DATE,
                "period": "future",
                "status": "pending",
                "initial_audit_status": None,
                "initial_missing_count": None,
                "pipeline_status": "pending",
                "pipeline_attempt_count": 0,
                "final_audit_status": None,
                "final_missing_count": None,
                "initial_audit": None,
                "final_audit": None,
                "error": None,
                "started_at": None,
                "completed_at": None,
                "updated_at": datetime.now(timezone.utc),
            },
        ]
    )
    return run


@pytest.mark.parametrize("initial_refresh_all_future", [False, True])
def test_reconciliation_store_reuses_only_same_mode_runs_and_preserves_resume_state(
    initial_refresh_all_future: bool,
):
    store, database = make_store()
    seed_run(database, refresh_all_future=initial_refresh_all_future)

    same_mode = store.enqueue(
        min_date=MIN_DATE,
        requested_max_date=MAX_DATE.isoformat(),
        future_horizon_days=365,
        audit_chunk_days=31,
        pipeline_chunk_days=7,
        max_attempts=3,
        source_quarantine_ttl_days=3,
        refresh_all_future=initial_refresh_all_future,
    )
    different_mode = store.enqueue(
        min_date=MIN_DATE,
        requested_max_date=MAX_DATE.isoformat(),
        future_horizon_days=365,
        audit_chunk_days=31,
        pipeline_chunk_days=7,
        max_attempts=3,
        source_quarantine_ttl_days=3,
        refresh_all_future=not initial_refresh_all_future,
    )
    persisted = store.get_run(int(same_mode["id"]))

    assert int(same_mode["id"]) == 1
    assert same_mode["status"] == "queued"
    assert same_mode["source_quarantine_ttl_days"] == 11
    assert same_mode["refresh_all_future"] is initial_refresh_all_future
    assert int(different_mode["id"]) == 2
    assert different_mode["refresh_all_future"] is not initial_refresh_all_future
    assert persisted["source_quarantine_ttl_days"] == 11
    assert persisted["refresh_all_future"] is initial_refresh_all_future
    assert persisted["started_at"] is not None
    assert len(persisted["dates"]) == 3
    assert persisted["dates"][0]["initial_audit"]["missing_count"] == 1
    assert persisted["dates"][0]["pipeline_attempt_count"] == 1


def test_reconciliation_worker_advisory_lock_is_single_owner_and_releasable():
    store, _database = make_store()
    first_lock = store.acquire_worker_lock()
    assert first_lock is not None
    second_lock = store.acquire_worker_lock()
    assert second_lock is None
    store.release_worker_lock(first_lock)
