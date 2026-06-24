from __future__ import annotations

import json
import os
import shlex
import sys
import time
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


EMPTY_IMPORT_METRICS = {
    "events_imported": 0,
    "artists_imported": 0,
    "event_payloads": 0,
    "event_tags": 0,
    "artist_tags": 0,
    "event_embeddings": 0,
    "artist_embeddings": 0,
}


def truncate_error(value: object, limit: int = 4000) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def import_log_connection() -> psycopg.Connection:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set")
    return psycopg.connect(database_url, row_factory=dict_row)


def ensure_import_log_schema(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS import_runs (
                id BIGSERIAL PRIMARY KEY,
                pipeline_name TEXT NOT NULL DEFAULT 'full-pipeline',
                status TEXT NOT NULL DEFAULT 'running',
                min_date DATE,
                max_date DATE,
                events_json TEXT,
                import_json TEXT,
                event_ids_file TEXT,
                artist_ids_file TEXT,
                event_count INTEGER NOT NULL DEFAULT 0,
                artist_count INTEGER NOT NULL DEFAULT 0,
                events_imported INTEGER NOT NULL DEFAULT 0,
                artists_imported INTEGER NOT NULL DEFAULT 0,
                event_payloads INTEGER NOT NULL DEFAULT 0,
                event_tags INTEGER NOT NULL DEFAULT 0,
                artist_tags INTEGER NOT NULL DEFAULT 0,
                event_embeddings INTEGER NOT NULL DEFAULT 0,
                artist_embeddings INTEGER NOT NULL DEFAULT 0,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                error TEXT,
                started_at TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP(6) WITH TIME ZONE,
                created_at TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT import_runs_status_check CHECK (status IN ('running', 'succeeded', 'failed'))
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS import_run_stages (
                id BIGSERIAL PRIMARY KEY,
                import_run_id BIGINT NOT NULL REFERENCES import_runs(id) ON DELETE CASCADE,
                stage_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                command TEXT,
                duration_ms INTEGER,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                error TEXT,
                started_at TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP(6) WITH TIME ZONE,
                created_at TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT import_run_stages_status_check CHECK (status IN ('running', 'succeeded', 'failed'))
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS import_runs_started_at_idx ON import_runs (started_at DESC)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS import_runs_status_started_at_idx ON import_runs (status, started_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS import_run_stages_run_stage_idx ON import_run_stages (import_run_id, stage_name)"
        )
        cursor.execute(
            """
            CREATE OR REPLACE VIEW import_run_latest_summary AS
            SELECT
                r.*,
                COALESCE(
                    (
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'stage', s.stage_name,
                                'status', s.status,
                                'durationMs', s.duration_ms,
                                'startedAt', s.started_at,
                                'finishedAt', s.finished_at,
                                'error', s.error
                            )
                            ORDER BY s.id
                        )
                        FROM import_run_stages s
                        WHERE s.import_run_id = r.id
                    ),
                    '[]'::jsonb
                ) AS stages
            FROM import_runs r
            ORDER BY r.started_at DESC
            """
        )
    connection.commit()


def fetch_count(connection: psycopg.Connection, query: str, params: tuple[Any, ...]) -> int:
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()
    if not row:
        return 0
    return int(next(iter(row.values())) or 0)


class ImportRunLogger:
    def __init__(self, run_id: int | None = None) -> None:
        self.run_id = run_id

    @property
    def enabled(self) -> bool:
        return self.run_id is not None

    @classmethod
    def disabled(cls) -> ImportRunLogger:
        return cls()

    @classmethod
    def start(
        cls,
        *,
        min_date: str,
        max_date: str,
        events_json: Path,
        event_ids_file: Path,
        artist_ids_file: Path,
        metadata: dict[str, Any],
    ) -> ImportRunLogger:
        try:
            with import_log_connection() as connection:
                ensure_import_log_schema(connection)
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO import_runs (
                            pipeline_name, status, min_date, max_date, events_json,
                            event_ids_file, artist_ids_file, metadata
                        )
                        VALUES ('full-pipeline', 'running', %s, %s, %s, %s, %s, %s::jsonb)
                        RETURNING id
                        """,
                        (
                            min_date,
                            max_date,
                            str(events_json),
                            str(event_ids_file),
                            str(artist_ids_file),
                            json.dumps(metadata),
                        ),
                    )
                    row = cursor.fetchone()
                connection.commit()
                run_id = int(row["id"])
            print(f"[pipeline] Import run log id={run_id}")
            return cls(run_id)
        except Exception as exc:
            print(f"[pipeline] Import run logging disabled: {exc}", file=sys.stderr)
            return cls.disabled()

    def start_stage(self, name: str, command: list[str]) -> tuple[int | None, float]:
        started_at = time.monotonic()
        if not self.enabled:
            return None, started_at
        try:
            with import_log_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO import_run_stages (import_run_id, stage_name, status, command)
                        VALUES (%s, %s, 'running', %s)
                        RETURNING id
                        """,
                        (self.run_id, name, shlex.join(command)),
                    )
                    row = cursor.fetchone()
                connection.commit()
                return int(row["id"]), started_at
        except Exception as exc:
            print(f"[pipeline] Could not start import stage log for {name}: {exc}", file=sys.stderr)
            return None, started_at

    def finish_stage(
        self,
        stage_id: int | None,
        *,
        status: str,
        started_at: float,
        error: object | None = None,
    ) -> None:
        if stage_id is None:
            return
        duration_ms = max(0, int((time.monotonic() - started_at) * 1000))
        try:
            with import_log_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE import_run_stages
                        SET status = %s,
                            duration_ms = %s,
                            error = %s,
                            finished_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (status, duration_ms, truncate_error(error) if error is not None else None, stage_id),
                    )
                connection.commit()
        except Exception as exc:
            print(f"[pipeline] Could not finish import stage log {stage_id}: {exc}", file=sys.stderr)

    def update(
        self,
        *,
        status: str | None = None,
        error: object | None = None,
        metrics: dict[str, Any] | None = None,
        import_json: Path | None = None,
    ) -> None:
        if not self.enabled:
            return
        values: dict[str, Any] = {}
        if status is not None:
            values["status"] = status
        if error is not None:
            values["error"] = truncate_error(error)
        if import_json is not None:
            values["import_json"] = str(import_json)
        if metrics:
            values.update(metrics)
        if status in {"succeeded", "failed"}:
            values["finished_at"] = "CURRENT_TIMESTAMP"
        if not values:
            return

        assignments: list[str] = []
        params: list[Any] = []
        for column, value in values.items():
            if value == "CURRENT_TIMESTAMP" and column == "finished_at":
                assignments.append(f"{column} = CURRENT_TIMESTAMP")
                continue
            assignments.append(f"{column} = %s")
            params.append(value)
        assignments.append("updated_at = CURRENT_TIMESTAMP")
        params.append(self.run_id)
        try:
            with import_log_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE import_runs SET {', '.join(assignments)} WHERE id = %s",
                        params,
                    )
                connection.commit()
        except Exception as exc:
            print(f"[pipeline] Could not update import run log {self.run_id}: {exc}", file=sys.stderr)

    def collect_metrics(self, event_ids: list[int], artist_ids: list[int]) -> dict[str, int]:
        event_ids_text = [str(event_id) for event_id in event_ids]
        artist_ids_text = [str(artist_id) for artist_id in artist_ids]
        if not event_ids_text and not artist_ids_text:
            return dict(EMPTY_IMPORT_METRICS)

        with import_log_connection() as connection:
            return {
                "events_imported": fetch_count(
                    connection,
                    "SELECT COUNT(*) FROM events WHERE ra_event_id = ANY(%s)",
                    (event_ids_text,),
                ),
                "artists_imported": fetch_count(
                    connection,
                    "SELECT COUNT(*) FROM artists WHERE ra_artist_id = ANY(%s)",
                    (artist_ids_text,),
                ),
                "event_payloads": fetch_count(
                    connection,
                    """
                    SELECT COUNT(*)
                    FROM event_source_payloads esp
                    JOIN events e ON e.id = esp.event_id
                    WHERE e.ra_event_id = ANY(%s)
                    """,
                    (event_ids_text,),
                ),
                "event_tags": fetch_count(
                    connection,
                    """
                    SELECT COUNT(*)
                    FROM event_extracted_tags t
                    JOIN events e ON e.id = t.event_id
                    WHERE e.ra_event_id = ANY(%s)
                    """,
                    (event_ids_text,),
                ),
                "artist_tags": fetch_count(
                    connection,
                    """
                    SELECT COUNT(*)
                    FROM artist_extracted_tags t
                    JOIN artists a ON a.id = t.artist_id
                    WHERE a.ra_artist_id = ANY(%s)
                    """,
                    (artist_ids_text,),
                ),
                "event_embeddings": fetch_count(
                    connection,
                    """
                    SELECT COUNT(*)
                    FROM entity_embeddings ee
                    JOIN events e ON e.id = ee.entity_id
                    WHERE ee.entity_type = 'event'
                      AND e.ra_event_id = ANY(%s)
                    """,
                    (event_ids_text,),
                ),
                "artist_embeddings": fetch_count(
                    connection,
                    """
                    SELECT COUNT(*)
                    FROM entity_embeddings ee
                    JOIN artists a ON a.id = ee.entity_id
                    WHERE ee.entity_type = 'artist'
                      AND a.ra_artist_id = ANY(%s)
                    """,
                    (artist_ids_text,),
                ),
            }
