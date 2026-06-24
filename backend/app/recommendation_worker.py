from __future__ import annotations

import logging
import time
from typing import Any

import psycopg

from app.db import DATABASE_URL, get_connection
from app.recommendation_jobs import (
    JOB_CREATED_CHANNEL,
    claim_next_recommendation_job,
    complete_recommendation_job,
    fail_recommendation_job,
    requeue_stale_running_jobs,
)
from app.recommendation_services import build_artist_promoter_recommendation_response
from app.schemas import RecommendationJobParams


logger = logging.getLogger(__name__)
RECONNECT_DELAY_SECONDS = 2.0


# Run the synchronous recommendation engine for one already claimed job.
def _run_job(job: dict[str, Any]) -> None:
    """Compute one claimed recommendation job and persist its terminal state."""
    job_id = str(job["id"])
    try:
        params = RecommendationJobParams.model_validate(job["params_json"])
        with get_connection() as connection:
            result = build_artist_promoter_recommendation_response(
                connection,
                artist_id=int(job["artist_id"]),
                limit=params.limit,
                exclude_existing=params.excludeExisting,
                debug=params.debug,
                user_id=int(job["user_id"]),
            )
            result_payload = result.model_dump(mode="json", exclude_none=True)

        with get_connection() as connection:
            complete_recommendation_job(
                connection,
                job_id=job_id,
                result=result_payload,
            )
        logger.info("Recommendation job %s completed", job_id)
    except Exception as error:
        logger.exception("Recommendation job %s failed", job_id)
        try:
            with get_connection() as connection:
                fail_recommendation_job(
                    connection,
                    job_id=job_id,
                    error_message=str(error) or error.__class__.__name__,
                )
        except Exception:
            logger.exception("Could not persist failure for recommendation job %s", job_id)


# Drain durable work after a notification, then return to blocking LISTEN.
def _drain_queued_jobs() -> None:
    """Process durable queued jobs until none remain, then return to blocking LISTEN."""
    while True:
        with get_connection() as connection:
            job = claim_next_recommendation_job(connection)
        if job is None:
            return
        _run_job(job)


# Keep a dedicated LISTEN connection open and reconnect after transient DB failures.
def run_worker() -> None:
    """Listen for job creation notifications and recover safely after DB reconnects."""
    while True:
        try:
            with psycopg.connect(DATABASE_URL, autocommit=True) as listener:
                listener.execute(f"LISTEN {JOB_CREATED_CHANNEL}")
                logger.info("Recommendation worker listening on %s", JOB_CREATED_CHANNEL)

                # Recover stale in-flight jobs left behind by a previously crashed worker.
                with get_connection() as connection:
                    requeue_stale_running_jobs(connection)

                # Jobs are durable, so process anything created while this worker was offline.
                _drain_queued_jobs()
                for _notification in listener.notifies():
                    with get_connection() as connection:
                        requeue_stale_running_jobs(connection)
                    _drain_queued_jobs()
        except KeyboardInterrupt:
            logger.info("Recommendation worker stopped")
            return
        except Exception:
            logger.exception(
                "Recommendation worker listener failed; reconnecting in %.1f seconds",
                RECONNECT_DELAY_SECONDS,
            )
            time.sleep(RECONNECT_DELAY_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_worker()
