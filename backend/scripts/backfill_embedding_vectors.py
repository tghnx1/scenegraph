import os
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ["DATABASE_URL"]


def main() -> None:
    configured_dimensions_raw = os.environ.get("OPENAI_EMBEDDING_DIMENSIONS", "").strip()
    configured_dimensions = int(configured_dimensions_raw) if configured_dimensions_raw else 1536

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(
                """
                ALTER TABLE IF EXISTS entity_embeddings
                ADD COLUMN IF NOT EXISTS embedding_vec vector(1536)
                """
            )
            cursor.execute(
                """
                UPDATE entity_embeddings
                SET embedding_vec = embedding::vector
                WHERE embedding_vec IS NULL
                  AND dimensions = %s
                """,
                (configured_dimensions,),
            )
            updated_rows = cursor.rowcount
            cursor.execute(
                """
                SELECT count(*)::int AS missing
                FROM entity_embeddings
                WHERE embedding_vec IS NULL
                  AND dimensions = %s
                """,
                (configured_dimensions,),
            )
            missing_rows = int(cursor.fetchone()["missing"])
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
        connection.commit()

    print(
        f"Embedding vector backfill complete: dimensions={configured_dimensions}, "
        f"updated={updated_rows}, remaining_missing={missing_rows}"
    )


if __name__ == "__main__":
    main()
