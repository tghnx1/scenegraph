"""Enqueue changed imported events without calling the model during ingestion."""

from __future__ import annotations

import psycopg
from psycopg import Connection

from app.promoter_role_backfill import MAX_EVENTS, create_run
from app.promoter_role_backfill import config_hash
from app.event_tag_extraction import EventTagExtractionConfig
from app.promoter_role_store import load_event_input
from app.promoter_roles import CLASSIFIER_VERSION, role_input_hash

ENQUEUE_LOCK = 0x534750524F4C4551


def enqueue_changed_events(connection: Connection, event_ids: tuple[int, ...], current_config_hash: str) -> tuple[int, ...]:
    """Create bounded runs only for changed events not already queued or running.

    The caller owns the transaction; the transaction lock serializes competing importers.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (ENQUEUE_LOCK,))
    pending: list[int] = []
    for event_id in sorted(set(event_ids)):
        event = load_event_input(connection, event_id)
        if event is None:
            continue
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                  SELECT 1 FROM promoter_event_classification
                  WHERE event_id = %s AND input_hash = %s AND config_hash = %s AND classifier_version = %s
                ), EXISTS (
                  SELECT 1 FROM promoter_role_backfill_item i
                  JOIN promoter_role_backfill_run r ON r.id = i.run_id
                  WHERE i.event_id = %s AND i.status IN ('pending', 'running')
                    AND r.status IN ('queued', 'running', 'paused')
                    AND r.config_hash = %s
                )
            """, (event_id, role_input_hash(event), current_config_hash, CLASSIFIER_VERSION, event_id, current_config_hash))
            fresh, queued = cursor.fetchone()
        if not fresh and not queued:
            pending.append(event_id)
    return tuple(create_run(connection, tuple(pending[i:i + MAX_EVENTS]), current_config_hash)
                 for i in range(0, len(pending), MAX_EVENTS))


def enqueue_imported_ra_events(database_url: str, ra_event_ids: tuple[str, ...]) -> tuple[int, ...]:
    """After a committed import, queue its changed events using ingestion's model."""
    if not ra_event_ids:
        return ()
    config = EventTagExtractionConfig.from_env()
    current_hash = config_hash(config.provider, config.model, config.reasoning_effort)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM events WHERE ra_event_id = ANY(%s) ORDER BY id", (list(ra_event_ids),))
            event_ids = tuple(int(row[0]) for row in cursor.fetchall())
        runs = enqueue_changed_events(connection, event_ids, current_hash)
        connection.commit()
        return runs
