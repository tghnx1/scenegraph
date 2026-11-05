"""Process bounded promoter-role jobs without tying them to ingestion."""

from __future__ import annotations

import logging
import os
import time

import psycopg

from app.event_tag_extraction import EventTagExtractionConfig
from app.promoter_role_backfill import BackfillBusy, extraction_config_hash, process_run
from app.promoter_roles import CLASSIFIER_VERSION

logger = logging.getLogger(__name__)


def process_next(connection: psycopg.Connection, current_hash: str) -> str | None:
    """Process one compatible queued or interrupted bounded run, if present."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id FROM promoter_role_backfill_run
            WHERE status IN ('queued', 'running') AND classifier_version = %s AND config_hash = %s
            ORDER BY CASE WHEN status = 'running' THEN 0 ELSE 1 END, id LIMIT 1
        """, (CLASSIFIER_VERSION, current_hash))
        row = cursor.fetchone()
    connection.commit()
    if row is None:
        return None
    return process_run(connection, int(row[0]), current_hash)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if os.environ.get("PROMOTER_ROLE_WORKER_ENABLED", "").strip().lower() != "true":
        logger.info("Promoter role worker is disabled")
        while True:
            time.sleep(3600)
    poll_seconds = max(5, int(os.environ.get("PROMOTER_ROLE_WORKER_POLL_SECONDS", "30")))
    while True:
        try:
            config = EventTagExtractionConfig.from_env()
            current_hash = extraction_config_hash(config)
            with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
                result = process_next(connection, current_hash)
            if result is not None:
                logger.info("Promoter role job finished with status=%s", result)
        except BackfillBusy:
            logger.info("Promoter role worker lock is busy")
        except (psycopg.Error, ValueError, KeyError):
            # Provider errors and connection strings can contain credentials; never log their text.
            logger.error("Promoter role worker configuration or database failure")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
