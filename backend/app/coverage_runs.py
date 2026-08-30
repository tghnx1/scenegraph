from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


# Separate from the full-pipeline lock. The worker stays single-consumer while
# each child full_pipeline invocation still acquires the existing pipeline lock.
COVERAGE_WORKER_ADVISORY_LOCK_KEY = 0x5347434F5657524B
COVERAGE_ENQUEUE_ADVISORY_LOCK_KEY = 0x5347434F56454E51
MAX_STORED_ERROR_CHARS = 1000


def compact_error(error: object | None) -> str | None:
    if error is None:
        return None
    if isinstance(error, BaseException):
        value = f"{type(error).__name__}: {error}"
    else:
        value = str(error)
    value = value.replace("\x00", "")
    for name, secret in os.environ.items():
        if secret and any(marker in name.upper() for marker in ("KEY", "SECRET", "TOKEN", "PASSWORD")):
            value = value.replace(secret, "[redacted]")
    return value[:MAX_STORED_ERROR_CHARS]


def iter_dates(min_date: date, max_date: date) -> Iterable[date]:
    current = min_date
    while current <= max_date:
        yield current
        current += timedelta(days=1)


class CoverageRunStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self, **kwargs: Any) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row, **kwargs)

    def enqueue(
        self,
        *,
        min_date: date,
        max_date: date,
        max_attempts: int,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(%s)",
                    (COVERAGE_ENQUEUE_ADVISORY_LOCK_KEY,),
                )
                cursor.execute(
                    """
                    SELECT *
                    FROM coverage_runs
                    WHERE min_date = %s
                      AND max_date = %s
                      AND status IN ('queued', 'running')
                    ORDER BY id DESC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (min_date, max_date),
                )
                existing = cursor.fetchone()
                if existing:
                    return dict(existing)
                cursor.execute(
                    """
                    INSERT INTO coverage_runs (min_date, max_date, max_attempts)
                    VALUES (%s, %s, %s)
                    RETURNING *
                    """,
                    (min_date, max_date, max_attempts),
                )
                run = dict(cursor.fetchone())
                cursor.executemany(
                    """
                    INSERT INTO coverage_run_dates (coverage_run_id, coverage_date)
                    VALUES (%s, %s)
                    ON CONFLICT (coverage_run_id, coverage_date) DO NOTHING
                    """,
                    [(run["id"], value) for value in iter_dates(min_date, max_date)],
                )
            connection.commit()
        return run

    def acquire_worker_lock(self) -> psycopg.Connection | None:
        connection = self._connect(autocommit=True)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_lock(%s) AS acquired",
                (COVERAGE_WORKER_ADVISORY_LOCK_KEY,),
            )
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
                cursor.execute(
                    "SELECT pg_advisory_unlock(%s)",
                    (COVERAGE_WORKER_ADVISORY_LOCK_KEY,),
                )
        finally:
            connection.close()

    def claim_next(self, worker_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM coverage_runs
                    WHERE status IN ('running', 'queued')
                    ORDER BY CASE WHEN status = 'running' THEN 0 ELSE 1 END, id
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                    """
                )
                row = cursor.fetchone()
                if not row:
                    return None
                cursor.execute(
                    """
                    UPDATE coverage_runs
                    SET status = 'running',
                        worker_id = %s,
                        started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                        completed_at = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING *
                    """,
                    (worker_id, row["id"]),
                )
                run = dict(cursor.fetchone())
            connection.commit()
        return run

    def get_run(self, run_id: int) -> dict[str, Any]:
        return self._fetch_run("WHERE r.id = %s", (run_id,))

    def get_latest(self) -> dict[str, Any]:
        return self._fetch_run("ORDER BY r.id DESC LIMIT 1", ())

    def _fetch_run(self, clause: str, params: tuple[Any, ...]) -> dict[str, Any]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT r.*
                    FROM coverage_runs r
                    {clause}
                    """,
                    params,
                )
                run = cursor.fetchone()
                if not run:
                    raise LookupError("Coverage run not found")
                cursor.execute(
                    """
                    SELECT *
                    FROM coverage_run_dates
                    WHERE coverage_run_id = %s
                    ORDER BY coverage_date
                    """,
                    (run["id"],),
                )
                dates = [dict(row) for row in cursor.fetchall()]
        result = dict(run)
        result["dates"] = dates
        return result

    def update_run(
        self,
        run_id: int,
        *,
        status: str | None = None,
        total_missing: int | None = None,
        error: object | None = None,
        completed: bool = False,
    ) -> None:
        assignments = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[Any] = []
        if status is not None:
            assignments.append("status = %s")
            params.append(status)
        if total_missing is not None:
            assignments.append("total_missing = %s")
            params.append(total_missing)
        if error is not None:
            assignments.append("error = %s")
            params.append(compact_error(error))
        elif status in {"running", "succeeded"}:
            assignments.append("error = NULL")
        if completed:
            assignments.append("completed_at = CURRENT_TIMESTAMP")
        params.append(run_id)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE coverage_runs SET {', '.join(assignments)} WHERE id = %s",
                    params,
                )
            connection.commit()

    def update_date(self, run_id: int, coverage_date: str, **values: Any) -> None:
        columns = {
            "status": "status",
            "initial_missing_count": "initial_missing_count",
            "final_missing_count": "final_missing_count",
            "audit_status": "audit_status",
            "backfill_status": "backfill_status",
            "backfill_attempt_count": "backfill_attempt_count",
            "verify_status": "verify_status",
            "verify_attempt_count": "verify_attempt_count",
            "initial_audit": "initial_audit",
            "final_audit": "final_audit",
            "error": "error",
        }
        unknown = set(values) - set(columns) - {"started", "completed"}
        if unknown:
            raise ValueError(f"Unsupported coverage date fields: {sorted(unknown)}")
        assignments = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[Any] = []
        for name, value in values.items():
            if name in {"started", "completed"}:
                continue
            assignments.append(f"{columns[name]} = %s")
            if name in {"initial_audit", "final_audit"} and value is not None:
                value = Jsonb(value)
            if name == "error":
                value = compact_error(value)
            params.append(value)
        if values.get("started"):
            assignments.append("started_at = COALESCE(started_at, CURRENT_TIMESTAMP)")
        if values.get("completed"):
            assignments.append("completed_at = CURRENT_TIMESTAMP")
        params.extend((run_id, coverage_date))
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE coverage_run_dates
                    SET {', '.join(assignments)}
                    WHERE coverage_run_id = %s AND coverage_date = %s::date
                    """,
                    params,
                )
            connection.commit()


def public_run_status(run: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        json.dumps(
            {
                "id": run["id"],
                "min_date": run["min_date"],
                "max_date": run["max_date"],
                "status": run["status"],
                "max_attempts": run["max_attempts"],
                "total_missing": run["total_missing"],
                "error": run["error"],
                "started_at": run["started_at"],
                "completed_at": run["completed_at"],
                "created_at": run["created_at"],
                "updated_at": run["updated_at"],
                "dates": [
                    {
                        "date": item["coverage_date"],
                        "status": item["status"],
                        "audit_status": item["audit_status"],
                        "initial_missing_count": item["initial_missing_count"],
                        "final_missing_count": item["final_missing_count"],
                        "backfill_status": item["backfill_status"],
                        "backfill_attempt_count": item["backfill_attempt_count"],
                        "verify_status": item["verify_status"],
                        "verify_attempt_count": item["verify_attempt_count"],
                        "error": item["error"],
                    }
                    for item in run["dates"]
                ],
            },
            default=str,
        )
    )
