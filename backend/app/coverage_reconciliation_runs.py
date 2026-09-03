from __future__ import annotations

import json
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.coverage_runs import compact_error, iter_dates


RECONCILIATION_WORKER_LOCK_KEY = 0x53475245434F4E57
RECONCILIATION_ENQUEUE_LOCK_KEY = 0x53475245434F4E45


class CoverageReconciliationStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self, **kwargs: Any) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row, **kwargs)

    def enqueue(
        self,
        *,
        min_date: date,
        requested_max_date: str,
        future_horizon_days: int,
        audit_chunk_days: int,
        pipeline_chunk_days: int,
        max_attempts: int,
        source_quarantine_ttl_days: int,
        refresh_all_future: bool = True,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (RECONCILIATION_ENQUEUE_LOCK_KEY,))
                cursor.execute(
                    """
                    SELECT * FROM coverage_reconciliations
                    WHERE requested_min_date = %s AND requested_max_date = %s
                      AND status IN ('queued', 'running', 'failed')
                    ORDER BY id DESC LIMIT 1 FOR UPDATE
                    """,
                    (min_date, requested_max_date),
                )
                existing = cursor.fetchone()
                if existing:
                    run = dict(existing)
                    if run["status"] == "failed":
                        cursor.execute(
                            """
                            UPDATE coverage_reconciliations
                            SET status = 'queued', error = NULL, completed_at = NULL,
                                worker_id = NULL, updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s RETURNING *
                            """,
                            (run["id"],),
                        )
                        run = dict(cursor.fetchone())
                    connection.commit()
                    return run
                cursor.execute(
                    """
                    INSERT INTO coverage_reconciliations (
                        requested_min_date, requested_max_date, future_horizon_days,
                        audit_chunk_days, pipeline_chunk_days, max_attempts,
                        source_quarantine_ttl_days, refresh_all_future
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
                    """,
                    (
                        min_date,
                        requested_max_date,
                        future_horizon_days,
                        audit_chunk_days,
                        pipeline_chunk_days,
                        max_attempts,
                        source_quarantine_ttl_days,
                        refresh_all_future,
                    ),
                )
                run = dict(cursor.fetchone())
            connection.commit()
        return run

    def initialize_dates(self, run_id: int, min_date: date, max_date: date, *, today: date) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO coverage_reconciliation_dates (
                        reconciliation_id, coverage_date, period
                    ) VALUES (%s, %s, %s)
                    ON CONFLICT (reconciliation_id, coverage_date) DO NOTHING
                    """,
                    [
                        (run_id, value, "historical" if value < today else "future")
                        for value in iter_dates(min_date, max_date)
                    ],
                )
            connection.commit()

    def acquire_worker_lock(self) -> psycopg.Connection | None:
        connection = self._connect(autocommit=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (RECONCILIATION_WORKER_LOCK_KEY,))
            row = cursor.fetchone()
        if row and row["acquired"]:
            return connection
        connection.close()
        return None

    @staticmethod
    def release_worker_lock(connection: psycopg.Connection | None) -> None:
        if connection is None:
            return
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (RECONCILIATION_WORKER_LOCK_KEY,))
        finally:
            connection.close()

    def claim_next(self, worker_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM coverage_reconciliations
                    WHERE status IN ('running', 'queued')
                    ORDER BY CASE WHEN status = 'running' THEN 0 ELSE 1 END, id
                    LIMIT 1 FOR UPDATE SKIP LOCKED
                    """
                )
                row = cursor.fetchone()
                if not row:
                    return None
                cursor.execute(
                    """
                    UPDATE coverage_reconciliations
                    SET status = 'running', worker_id = %s,
                        started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                        completed_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s RETURNING *
                    """,
                    (worker_id, row["id"]),
                )
                run = dict(cursor.fetchone())
            connection.commit()
        return run

    def get_run(self, run_id: int) -> dict[str, Any]:
        return self._fetch("WHERE r.id = %s", (run_id,))

    def get_latest(self) -> dict[str, Any]:
        return self._fetch("ORDER BY r.id DESC LIMIT 1", ())

    def _fetch(self, clause: str, params: tuple[Any, ...]) -> dict[str, Any]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT r.* FROM coverage_reconciliations r {clause}", params)
                run = cursor.fetchone()
                if not run:
                    raise LookupError("Coverage reconciliation not found")
                cursor.execute(
                    """
                    SELECT * FROM coverage_reconciliation_dates
                    WHERE reconciliation_id = %s ORDER BY coverage_date
                    """,
                    (run["id"],),
                )
                dates = [dict(row) for row in cursor.fetchall()]
        result = dict(run)
        result["dates"] = dates
        return result

    def update_run(self, run_id: int, *, completed: bool = False, **values: Any) -> None:
        columns = {
            "resolved_max_date", "status", "phase", "current_min_date", "current_max_date",
            "initial_missing", "final_missing", "worker_id", "error",
        }
        unknown = set(values) - columns
        if unknown:
            raise ValueError(f"Unsupported reconciliation fields: {sorted(unknown)}")
        assignments = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[Any] = []
        for name, value in values.items():
            assignments.append(f"{name} = %s")
            params.append(compact_error(value) if name == "error" else value)
        if values.get("status") in {"running", "succeeded"} and "error" not in values:
            assignments.append("error = NULL")
        if values.get("status") == "running":
            assignments.append("started_at = COALESCE(started_at, CURRENT_TIMESTAMP)")
        if completed:
            assignments.append("completed_at = CURRENT_TIMESTAMP")
        params.append(run_id)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE coverage_reconciliations SET {', '.join(assignments)} WHERE id = %s",
                    params,
                )
            connection.commit()

    def update_date(self, run_id: int, coverage_date: str, *, completed: bool = False, **values: Any) -> None:
        columns = {
            "status", "initial_audit_status", "initial_missing_count", "pipeline_status",
            "pipeline_attempt_count", "final_audit_status", "final_missing_count",
            "initial_audit", "final_audit", "error",
        }
        unknown = set(values) - columns
        if unknown:
            raise ValueError(f"Unsupported reconciliation date fields: {sorted(unknown)}")
        assignments = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[Any] = []
        for name, value in values.items():
            assignments.append(f"{name} = %s")
            if name in {"initial_audit", "final_audit"} and value is not None:
                value = Jsonb(value)
            if name == "error":
                value = compact_error(value)
            params.append(value)
        if values.get("status") == "processing":
            assignments.append("started_at = COALESCE(started_at, CURRENT_TIMESTAMP)")
        if completed:
            assignments.append("completed_at = CURRENT_TIMESTAMP")
        params.extend((run_id, coverage_date))
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE coverage_reconciliation_dates SET {', '.join(assignments)}
                    WHERE reconciliation_id = %s AND coverage_date = %s::date
                    """,
                    params,
                )
            connection.commit()


def public_reconciliation_status(run: dict[str, Any], *, verbose: bool = False) -> dict[str, Any]:
    dates = run.get("dates", [])
    result = {
        "id": run["id"],
        "status": run["status"],
        "phase": run["phase"],
        "requested_min_date": run["requested_min_date"],
        "requested_max_date": run["requested_max_date"],
        "resolved_max_date": run["resolved_max_date"],
        "current_min_date": run["current_min_date"],
        "current_max_date": run["current_max_date"],
        "initial_missing": run["initial_missing"],
        "final_missing": run["final_missing"],
        "refresh_all_future": run["refresh_all_future"],
        "error": run["error"],
        "dates_total": len(dates),
        "dates_initially_audited": sum(item["initial_audit_status"] is not None for item in dates),
        "historical_repairs_complete": sum(
            item["period"] == "historical" and item["pipeline_status"] in {"succeeded", "skipped"}
            for item in dates
        ),
        "future_refresh_complete": sum(
            item["period"] == "future" and item["pipeline_status"] == "succeeded"
            for item in dates
        ),
        "final_audits_complete": sum(item["final_audit_status"] is not None for item in dates),
        "started_at": run["started_at"],
        "completed_at": run["completed_at"],
        "updated_at": run["updated_at"],
    }
    if verbose:
        result["dates"] = dates
    return json.loads(json.dumps(result, default=str))
