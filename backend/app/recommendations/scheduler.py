from __future__ import annotations

import logging

from app.db import get_connection
from app.embeddings import EmbeddingConfig
from app.recommendations.jobs import (
    enqueue_default_artist_promoter_recommendation_job,
)


logger = logging.getLogger(__name__)


def _eligible_recommendation_targets(connection) -> list[dict[str, int]]:
    embedding_config = EmbeddingConfig.from_env()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                u.id AS user_id,
                u.artist_id AS artist_id,
                u.role AS role,
                u.status AS status,
                COALESCE(
                    NULLIF(BTRIM(COALESCE(a.biography_normalized, a.biography, '')), ''),
                    ''
                ) <> '' AS has_biography,
                EXISTS(
                    SELECT 1
                    FROM entity_embeddings ee
                    WHERE ee.entity_type = 'artist'
                      AND ee.entity_id = a.id
                      AND ee.model = %s
                      AND ee.dimensions = %s
                ) AS has_current_embedding,
                (
                    SELECT COUNT(DISTINCT amc.connected_artist_id)
                    FROM artist_manual_connections amc
                    WHERE amc.source_artist_id = a.id
                ) AS manual_connection_count
            FROM users u
            JOIN artists a ON a.id = u.artist_id
            WHERE u.artist_id IS NOT NULL
              AND u.role = 'artist'
              AND u.status = 'approved'
            ORDER BY u.id ASC
            """,
            (embedding_config.provider_model_key, embedding_config.dimensions),
        )
        rows = cursor.fetchall()

    return [
        {
            "user_id": int(row["user_id"]),
            "artist_id": int(row["artist_id"]),
        }
        for row in rows
        if str(row.get("role")) == "artist"
        and str(row.get("status")) == "approved"
        if bool(row["has_biography"])
        and bool(row["has_current_embedding"])
        and int(row["manual_connection_count"]) >= 3
    ]


def run_scheduler() -> int:
    enqueued = 0
    with get_connection() as connection:
        targets = _eligible_recommendation_targets(connection)
        for target in targets:
            enqueue_default_artist_promoter_recommendation_job(
                connection,
                user_id=target["user_id"],
                artist_id=target["artist_id"],
            )
            enqueued += 1
        connection.commit()

    logger.info("Recommendation scheduler processed %s eligible artist accounts", enqueued)
    return enqueued


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_scheduler()


if __name__ == "__main__":
    main()
