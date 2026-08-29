from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from psycopg import Connection
import psycopg
from psycopg.rows import dict_row

from app.artist_tag_extraction import is_content_filter_error


def classify_extraction_error(error: BaseException) -> str | None:
    """Return a quarantine type only for known, entity-scoped extraction failures."""
    if is_content_filter_error(error):
        return "content_filter"
    if isinstance(error, json.JSONDecodeError):
        return "malformed_json"
    return None


def quarantine_entity(
    connection: Connection,
    *,
    entity_type: str,
    entity_id: int,
    stage: str,
    error: BaseException,
    metadata: dict[str, Any] | None = None,
) -> None:
    error_type = classify_extraction_error(error) or type(error).__name__
    details = dict(metadata or {})
    details.setdefault("reason", error_type)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO ingestion_quarantine (
                entity_type, entity_id, stage, error_type, error_message, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (entity_type, entity_id, stage) WHERE resolved_at IS NULL
            DO UPDATE SET
                error_type = EXCLUDED.error_type,
                error_message = EXCLUDED.error_message,
                attempt_count = ingestion_quarantine.attempt_count + 1,
                last_seen_at = CURRENT_TIMESTAMP,
                metadata = EXCLUDED.metadata
            """,
            (
                entity_type,
                entity_id,
                stage,
                error_type,
                str(error)[:4000],
                json.dumps(details),
            ),
        )
    connection.commit()


def resolve_quarantine(
    connection: Connection,
    *,
    entity_type: str,
    entity_id: int,
    stage: str,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE ingestion_quarantine
            SET resolved_at = CURRENT_TIMESTAMP,
                last_seen_at = CURRENT_TIMESTAMP
            WHERE entity_type = %s
              AND entity_id = %s
              AND stage = %s
              AND resolved_at IS NULL
            """,
            (entity_type, entity_id, stage),
        )
    connection.commit()


def fetch_run_quarantine_summary(database_url: str, *, since: datetime) -> dict[str, int]:
    """Return unresolved quarantine rows touched since the start of this pipeline run."""
    with psycopg.connect(database_url or os.environ.get("DATABASE_URL", ""), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT entity_type, COUNT(*) AS count
                FROM ingestion_quarantine
                WHERE resolved_at IS NULL AND last_seen_at >= %s
                GROUP BY entity_type
                """,
                (since,),
            )
            rows = cursor.fetchall()
    summary = {"event": 0, "artist": 0, "total": 0}
    for row in rows:
        entity_type = str(row["entity_type"])
        count = int(row["count"])
        if entity_type in summary:
            summary[entity_type] = count
        summary["total"] += count
    return summary
