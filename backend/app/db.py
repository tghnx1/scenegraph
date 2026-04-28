import os
from collections.abc import Generator

import psycopg
from psycopg.rows import dict_row


DATABASE_URL = os.environ["DATABASE_URL"]


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def get_db() -> Generator[psycopg.Connection, None, None]:
    with get_connection() as connection:
        yield connection


def initialize_database() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS venues (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    district TEXT NOT NULL,
                    scene_focus TEXT NOT NULL
                )
                """
            )
            cursor.execute("SELECT COUNT(*) AS count FROM venues")
            existing_count = cursor.fetchone()["count"]

            if existing_count == 0:
                cursor.executemany(
                    """
                    INSERT INTO venues (name, district, scene_focus)
                    VALUES (%s, %s, %s)
                    """,
                    [
                        ("OHM", "Mitte", "Techno and leftfield club nights"),
                        ("://about blank", "Friedrichshain", "Community-driven electronic music"),
                        ("Minimal Bar", "Kreuzberg", "House, minimal, and local DJ nights"),
                    ],
                )

        connection.commit()
