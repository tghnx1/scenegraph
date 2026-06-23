from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb


JOB_CREATED_CHANNEL = "scenegraph_recommendation_job_created"
JOB_UPDATED_CHANNEL = "scenegraph_recommendation_job_updated"
ARTIST_PROMOTERS_JOB_TYPE = "artist_promoters"


# Build a stable signature for the stored parameters without deduplicating jobs.
def _params_hash(params: dict[str, Any]) -> str:
    """Return a deterministic fingerprint for the recommendation job parameters."""
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


# Build the compact event used to route a status update to the owning user.
def _notification_payload(row: dict[str, Any]) -> str:
    """Serialize the small job event shared by PostgreSQL and WebSocket listeners."""
    return json.dumps(
        {
            "type": "recommendation.job.updated",
            "jobId": str(row["id"]),
            "userId": int(row["user_id"]),
            "status": row["status"],
        },
        separators=(",", ":"),
    )


# Enqueue a PostgreSQL notification inside the caller's current transaction.
def _notify(connection: Connection, channel: str, payload: str) -> None:
    """Queue a PostgreSQL notification that is delivered only after transaction commit."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_notify(%s, %s)", (channel, payload))


# Store a queued Artist -> Promoters job and wake workers after commit.
def create_recommendation_job(
    connection: Connection,
    *,
    user_id: int,
    artist_id: int,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Persist a queued Artist -> Promoters job and wake sleeping workers after commit."""
    params_hash = _params_hash(params)
    job_id = uuid.uuid4()
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO recommendation_jobs (
                    id,
                    user_id,
                    artist_id,
                    job_type,
                    params_hash,
                    params_json,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'queued')
                RETURNING *
                """,
                (
                    job_id,
                    user_id,
                    artist_id,
                    ARTIST_PROMOTERS_JOB_TYPE,
                    params_hash,
                    Jsonb(params),
                ),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to create recommendation job")
        _notify(
            connection,
            JOB_CREATED_CHANNEL,
            json.dumps({"jobId": str(job_id)}, separators=(",", ":")),
        )
    return row


# Read a job only when it belongs to the authenticated user.
def get_recommendation_job(
    connection: Connection,
    *,
    job_id: str,
    user_id: int,
) -> dict[str, Any] | None:
    """Return one job only when it belongs to the authenticated user."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT *
            FROM recommendation_jobs
            WHERE id = %s::uuid
              AND user_id = %s
            """,
            (job_id, user_id),
        )
        return cursor.fetchone()


# Claim one queued job atomically without waiting for another worker's row lock.
def claim_next_recommendation_job(connection: Connection) -> dict[str, Any] | None:
    """Atomically claim the oldest queued job without blocking other workers."""
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM recommendation_jobs
                WHERE status = 'queued'
                ORDER BY created_at ASC, id ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """
            )
            candidate = cursor.fetchone()
            if candidate is None:
                return None

            cursor.execute(
                """
                UPDATE recommendation_jobs
                SET status = 'running',
                    started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                    finished_at = NULL,
                    error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *
                """,
                (candidate["id"],),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Claimed recommendation job disappeared")
        _notify(connection, JOB_UPDATED_CHANNEL, _notification_payload(row))
    return row


# Persist a completed result and emit its status after commit.
def complete_recommendation_job(
    connection: Connection,
    *,
    job_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Store the final recommendation payload and publish a completed event after commit."""
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recommendation_jobs
                SET status = 'completed',
                    result_json = %s,
                    error_message = NULL,
                    finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                  AND status = 'running'
                RETURNING *
                """,
                (Jsonb(result), job_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError(f"Running recommendation job {job_id} was not found")
        _notify(connection, JOB_UPDATED_CHANNEL, _notification_payload(row))
    return row


# Persist a terminal error and emit its status after commit.
def fail_recommendation_job(
    connection: Connection,
    *,
    job_id: str,
    error_message: str,
) -> dict[str, Any]:
    """Persist a terminal failure and notify the owning user's WebSocket connection."""
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recommendation_jobs
                SET status = 'failed',
                    result_json = NULL,
                    error_message = %s,
                    finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                  AND status = 'running'
                RETURNING *
                """,
                (error_message[:2000], job_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError(f"Running recommendation job {job_id} was not found")
        _notify(connection, JOB_UPDATED_CHANNEL, _notification_payload(row))
    return row
