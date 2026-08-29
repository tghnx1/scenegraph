from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from app.artist_tag_extraction import is_content_filter_error


def classify_extraction_error(error: BaseException) -> str | None:
    """Return a quarantine type only for known, entity-scoped extraction failures."""
    if is_content_filter_error(error):
        return "content_filter"
    if isinstance(error, json.JSONDecodeError):
        return "malformed_json"
    return None


def extraction_error_metadata(error: BaseException, *, provider: str = "azure") -> dict[str, str]:
    error_type = classify_extraction_error(error)
    metadata = {"provider": provider, "reason": error_type or type(error).__name__}
    if error_type != "content_filter":
        return metadata

    body = getattr(error, "body", None)
    if not isinstance(body, dict):
        return metadata
    error_body = body.get("error") if isinstance(body.get("error"), dict) else body
    inner = error_body.get("innererror") if isinstance(error_body, dict) else None
    if not isinstance(inner, dict):
        return metadata
    filter_result = inner.get("content_filter_result")
    if not isinstance(filter_result, dict):
        return metadata

    for category, details in filter_result.items():
        if not isinstance(details, dict) or not details.get("filtered"):
            continue
        metadata["filter_category"] = str(category)[:80]
        severity = details.get("severity")
        if severity is not None:
            metadata["filter_severity"] = str(severity)[:40]
        break
    return metadata


def safe_extraction_error_message(error: BaseException) -> str:
    error_type = classify_extraction_error(error)
    if error_type == "content_filter":
        return "Provider rejected entity content under content_filter policy"
    if isinstance(error, json.JSONDecodeError):
        return (
            f"{error.msg}: line {error.lineno} column {error.colno} "
            f"(char {error.pos})"
        )[:1000]
    return f"{type(error).__name__}: {str(error)[:900]}"


def quarantine_entity(
    connection: Connection,
    *,
    entity_type: str,
    entity_id: int,
    stage: str,
    error: BaseException,
    metadata: dict[str, Any] | None = None,
) -> int:
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
            RETURNING attempt_count
            """,
            (
                entity_type,
                entity_id,
                stage,
                error_type,
                safe_extraction_error_message(error),
                json.dumps(details),
            ),
        )
        row = cursor.fetchone()
    connection.commit()
    if not row:
        raise RuntimeError("Quarantine upsert did not return an attempt count")
    return int(row["attempt_count"])


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
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
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


def fetch_unresolved_quarantine(
    database_url: str,
    *,
    entity_type: str | None = None,
    stage: str | None = None,
    entity_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    conditions = ["resolved_at IS NULL"]
    params: list[Any] = []
    if entity_type is not None:
        conditions.append("entity_type = %s")
        params.append(entity_type)
    if stage is not None:
        conditions.append("stage = %s")
        params.append(stage)
    if entity_id is not None:
        conditions.append("entity_id = %s")
        params.append(entity_id)
    params.append(limit)

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, entity_type, entity_id, stage, error_type, error_message,
                       attempt_count, first_seen_at, last_seen_at, metadata
                FROM ingestion_quarantine
                WHERE {' AND '.join(conditions)}
                ORDER BY last_seen_at ASC, id ASC
                LIMIT %s
                """,
                params,
            )
            return list(cursor.fetchall())
