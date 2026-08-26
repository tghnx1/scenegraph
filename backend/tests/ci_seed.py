from __future__ import annotations

import os

import psycopg


DATABASE_URL = os.environ["DATABASE_URL"]


def main() -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO artists (id, ra_artist_id, name)
                VALUES
                    (2178, 'ci-source-artist', 'CI Source Artist'),
                    (2179, 'ci-connected-artist', 'CI Connected Artist')
                ON CONFLICT DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO users (id, username, email, password_hash, role, status)
                VALUES (1, 'ci-admin', 'ci-admin@example.com', 'ci-password-hash', 'admin', 'approved')
                ON CONFLICT DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO promoters (id, ra_promoter_id, name, live)
                VALUES (9700001, 'ci-promoter', 'CI Promoter', TRUE)
                ON CONFLICT DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO events (id, ra_event_id, title, event_date, interested_count, live)
                VALUES
                    (9800001, 'ci-shared-event', 'CI Shared Event', CURRENT_TIMESTAMP - INTERVAL '30 days', 25, TRUE),
                    (9800002, 'ci-promoted-event', 'CI Promoted Event', CURRENT_TIMESTAMP - INTERVAL '20 days', 50, TRUE)
                ON CONFLICT DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO event_artists (event_id, artist_id)
                VALUES
                    (9800001, 2178),
                    (9800001, 2179),
                    (9800002, 2179)
                ON CONFLICT DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO event_promoters (event_id, promoter_id)
                VALUES (9800002, 9700001)
                ON CONFLICT DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO entity_embeddings (
                    entity_type,
                    entity_id,
                    model,
                    dimensions,
                    text_hash,
                    text_profile,
                    embedding,
                    embedding_vec
                )
                VALUES
                    (
                        'artist',
                        2178,
                        'openai:text-embedding-3-small',
                        1536,
                        'ci-source-hash',
                        'CI Source Artist',
                        array_fill(0.01::double precision, ARRAY[1536]),
                        array_fill(0.01::real, ARRAY[1536])::vector
                    ),
                    (
                        'artist',
                        2179,
                        'openai:text-embedding-3-small',
                        1536,
                        'ci-connected-hash',
                        'CI Connected Artist',
                        array_fill(0.01::double precision, ARRAY[1536]),
                        array_fill(0.01::real, ARRAY[1536])::vector
                    )
                ON CONFLICT DO NOTHING
                """
            )
            for table in ("artists", "users", "promoters", "events"):
                cursor.execute(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table}', 'id'),
                        (SELECT max(id) FROM {table}),
                        TRUE
                    )
                    """
                )

    print("Seeded disposable CI recommendation graph")


if __name__ == "__main__":
    main()
