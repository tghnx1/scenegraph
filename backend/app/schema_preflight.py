from __future__ import annotations

import os
from datetime import datetime, timezone

from psycopg import Connection


REQUIRED_TABLES: tuple[str, ...] = (
    "artists",
    "events",
    "venues",
    "genres",
    "promoters",
    "event_artists",
    "event_genres",
    "event_images",
    "event_promoters",
    "event_source_payloads",
    "entity_embeddings",
    "artist_extracted_tags",
    "artist_tag_extraction_runs",
    "event_extracted_tags",
    "event_tag_extraction_runs",
    "recommendation_feedback",
)

OPTIONAL_TABLES: tuple[str, ...] = (
    # The recommendations pipeline can gracefully run without this table.
    "artist_manual_connections",
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def schema_preflight_strict_mode() -> bool:
    return _env_bool("SCHEMA_PREFLIGHT_STRICT", True)


def check_schema_tables(connection: Connection) -> dict[str, object]:
    expected_tables = [*REQUIRED_TABLES, *OPTIONAL_TABLES]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            (expected_tables,),
        )
        existing = {row["table_name"] for row in cursor.fetchall()}

    missing_required = sorted(table for table in REQUIRED_TABLES if table not in existing)
    missing_optional = sorted(table for table in OPTIONAL_TABLES if table not in existing)

    if missing_required:
        status = "error"
    elif missing_optional:
        status = "degraded"
    else:
        status = "ok"

    return {
        "status": status,
        "checkedAt": datetime.now(tz=timezone.utc).isoformat(),
        "requiredTableCount": len(REQUIRED_TABLES),
        "optionalTableCount": len(OPTIONAL_TABLES),
        "missingRequiredTables": missing_required,
        "missingOptionalTables": missing_optional,
    }

