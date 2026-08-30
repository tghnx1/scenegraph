from __future__ import annotations

import psycopg


# ASCII "SCENEGRA" interpreted as a signed-safe PostgreSQL bigint.
PIPELINE_ADVISORY_LOCK_KEY = 0x5343454E45475241


class PipelineAlreadyRunningError(RuntimeError):
    pass


def acquire_pipeline_lock(database_url: str) -> psycopg.Connection:
    connection = psycopg.connect(database_url, autocommit=True)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (PIPELINE_ADVISORY_LOCK_KEY,))
            row = cursor.fetchone()
        acquired = bool(row.get("acquired") if isinstance(row, dict) else row[0] if row else False)
        if not acquired:
            raise PipelineAlreadyRunningError("Another ingestion/full pipeline run currently holds the pipeline lock")
        return connection
    except BaseException:
        connection.close()
        raise


def release_pipeline_lock(connection: psycopg.Connection | None) -> None:
    if connection is None:
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", (PIPELINE_ADVISORY_LOCK_KEY,))
    finally:
        connection.close()
