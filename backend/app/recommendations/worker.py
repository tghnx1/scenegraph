from __future__ import annotations

import logging
import os
import time
from typing import Any

import psycopg

from app.db import DATABASE_URL, get_connection
from app.artist_refresh import refresh_artist_derived_data
from app.recommendations.jobs import (
    ARTIST_BIO_REFRESH_JOB_TYPE,
    ARTIST_PROMOTERS_JOB_TYPE,
    JOB_CREATED_CHANNEL,
    claim_next_recommendation_job,
    complete_recommendation_job,
    enqueue_user_artist_promoter_recommendation_job,
    fail_recommendation_job,
    requeue_stale_running_jobs,
    role_aware_params_hash,
)
from app.promoter_role_runtime import resolve_runtime_context
from app.recommendations.role_aware import build_role_aware_recommendations
from app.recommendations.services import build_artist_promoter_recommendation_response
from app.event_tag_extraction import EventTagExtractionConfig
from app.promoter_role_backfill import extraction_config_hash
from app.promoter_role_shadow import compare_recommendations, store_shadow_comparison
from app.schemas import PromoterRecommendationResponse, RecommendationJobParams


logger = logging.getLogger(__name__)
RECONNECT_DELAY_SECONDS = 2.0


def _shadow_allowed(user_id: int) -> bool:
    if os.environ.get("PROMOTER_ROLE_SHADOW_ENABLED", "").strip().lower() != "true":
        return False
    values = (value.strip() for value in os.environ.get("PROMOTER_ROLE_SHADOW_USER_IDS", "").split(","))
    allowed = {int(value) for value in values if value.isascii() and value.isdigit() and len(value) <= 19}
    return user_id in allowed


def _run_optional_shadow(connection: psycopg.Connection, job: dict[str, Any], params: RecommendationJobParams,
                         baseline: PromoterRecommendationResponse) -> None:
    """Compare only explicitly allowed users; never replace or fail the primary result."""
    user_id = int(job["user_id"])
    if not _shadow_allowed(user_id):
        return
    try:
        with connection.transaction():
            connection.execute("SET LOCAL statement_timeout = '30s'")
            config = EventTagExtractionConfig.from_env()
            current_hash = extraction_config_hash(config)
            comparison = compare_recommendations(
                connection, artist_id=int(job["artist_id"]), user_id=user_id, limit=params.limit,
                current_config_hash=current_hash, builder=build_artist_promoter_recommendation_response,
                baseline=baseline,
            )
            store_shadow_comparison(connection, artist_id=int(job["artist_id"]), user_id=user_id,
                                    current_config_hash=current_hash, result=comparison,
                                    recommendation_job_id=str(job["id"]))
    except Exception as error:
        # This boundary is optional and isolated by a savepoint; do not log provider or DB details.
        logger.warning("Promoter shadow comparison failed: %s", type(error).__name__)


# Run the synchronous recommendation engine for one already claimed job.
def _run_job(job: dict[str, Any]) -> None:
    """Compute one claimed recommendation job and persist its terminal state."""
    job_id = str(job["id"])
    try:
        job_type = str(job["job_type"])
        shadow_input = None
        with get_connection() as connection:
            if job_type == ARTIST_PROMOTERS_JOB_TYPE:
                params = RecommendationJobParams.model_validate(job["params_json"])
                result = build_role_aware_recommendations(
                    connection,
                    artist_id=int(job["artist_id"]),
                    limit=params.limit,
                    debug=params.debug,
                    user_id=int(job["user_id"]),
                )
                result_payload = result.model_dump(mode="json", exclude_none=True)
                shadow_input = (params, result)
            elif job_type == ARTIST_BIO_REFRESH_JOB_TYPE:
                result_payload = refresh_artist_derived_data(
                    connection,
                    artist_id=int(job["artist_id"]),
                )
                enqueue_user_artist_promoter_recommendation_job(
                    connection,
                    user_id=int(job["user_id"]),
                    artist_id=int(job["artist_id"]),
                )
            else:
                raise RuntimeError(f"Unsupported recommendation job type: {job_type}")

        with get_connection() as connection:
            if job_type == ARTIST_PROMOTERS_JOB_TYPE:
                context = resolve_runtime_context(connection, user_id=int(job["user_id"]), lock=True)
                if job["params_hash"] != role_aware_params_hash(job["params_json"], context):
                    raise RuntimeError("Promoter recommendation job is stale; request a new calculation")
            complete_recommendation_job(
                connection,
                job_id=job_id,
                result=result_payload,
            )
        logger.info("Recommendation job %s completed", job_id)
        if shadow_input is not None and _shadow_allowed(int(job["user_id"])):
            try:
                with get_connection() as connection:
                    _run_optional_shadow(connection, job, *shadow_input)
            except Exception as error:
                # The primary result is already committed; never mark it failed for shadow errors.
                logger.warning("Promoter shadow connection failed: %s", type(error).__name__)
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
