from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.embeddings import fetch_entity_ids

DATABASE_URL = os.environ["DATABASE_URL"]


def load_id_file(path: Path | None) -> list[int] | None:
    if path is None:
        return None
    if not path.exists():
        raise SystemExit(f"ID file not found: {path}")
    ids: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            ids.append(int(raw))
        except ValueError as exc:
            raise SystemExit(f"Invalid integer id in {path}: {raw}") from exc
    return ids


def update_entity_vectors(
    connection: psycopg.Connection,
    *,
    entity_type: str,
    entity_ids: list[int] | None,
    configured_dimensions: int,
) -> tuple[int, int]:
    if entity_ids is not None and not entity_ids:
        return 0, 0

    with connection.cursor() as cursor:
        params: list[object] = [configured_dimensions, entity_type]
        where = ["dimensions = %s", "entity_type = %s", "embedding_vec IS NULL"]
        if entity_ids is not None:
            where.append("entity_id = ANY(%s)")
            params.append(entity_ids)

        cursor.execute(
            f"""
            UPDATE entity_embeddings
            SET embedding_vec = embedding::vector
            WHERE {' AND '.join(where)}
            """,
            params,
        )
        updated_rows = cursor.rowcount

        cursor.execute(
            f"""
            SELECT count(*)::int AS missing
            FROM entity_embeddings
            WHERE {' AND '.join(where)}
            """,
            params,
        )
        missing_rows = int(cursor.fetchone()["missing"])

    return updated_rows, missing_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill embedding vectors for stored entity embeddings.")
    parser.add_argument("--event-ids-file", type=Path, default=None, help="Optional newline-delimited event ids.")
    parser.add_argument("--artist-ids-file", type=Path, default=None, help="Optional newline-delimited artist ids.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configured_dimensions_raw = os.environ.get("OPENAI_EMBEDDING_DIMENSIONS", "").strip()
    if not configured_dimensions_raw:
        raise SystemExit("OPENAI_EMBEDDING_DIMENSIONS must be set")
    configured_dimensions = int(configured_dimensions_raw)
    event_ids = load_id_file(args.event_ids_file)
    artist_ids = load_id_file(args.artist_ids_file)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(
                """
                ALTER TABLE IF EXISTS entity_embeddings
                ADD COLUMN IF NOT EXISTS embedding_vec vector(%s)
                """,
                (configured_dimensions,),
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS entity_embeddings_vector_hnsw_cosine_idx
                ON entity_embeddings
                USING hnsw (embedding_vec vector_cosine_ops)
                WHERE embedding_vec IS NOT NULL
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS entity_embeddings_vector_lookup_idx
                ON entity_embeddings (entity_type, model, dimensions, entity_id)
                WHERE embedding_vec IS NOT NULL
                """
            )

        event_entity_ids = fetch_entity_ids(connection, "event", ids=event_ids)
        artist_entity_ids = fetch_entity_ids(connection, "artist", ids=artist_ids)
        event_updated, event_missing = update_entity_vectors(
            connection,
            entity_type="event",
            entity_ids=event_entity_ids,
            configured_dimensions=configured_dimensions,
        )
        artist_updated, artist_missing = update_entity_vectors(
            connection,
            entity_type="artist",
            entity_ids=artist_entity_ids,
            configured_dimensions=configured_dimensions,
        )
        updated_rows = event_updated + artist_updated
        missing_rows = event_missing + artist_missing
        connection.commit()

    print(
        f"Embedding vector backfill complete: dimensions={configured_dimensions}, "
        f"updated={updated_rows}, remaining_missing={missing_rows}"
    )


if __name__ == "__main__":
    main()
