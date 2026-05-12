import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.import_events import normalize_lineup_text


DATABASE_URL = os.environ["DATABASE_URL"]


def assert_lineup_residual_column(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'events'
              AND column_name = 'lineup_residual_text'
            """
        )
        if cursor.fetchone() is None:
            raise SystemExit(
                "events.lineup_residual_text does not exist. "
                "Run `make prisma-migrate` before backfilling."
            )


def main() -> None:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        assert_lineup_residual_column(connection)

        with connection.cursor() as cursor:
            cursor.execute("SELECT id, lineup_raw FROM events WHERE lineup_raw IS NOT NULL")
            rows = cursor.fetchall()

            updated = 0
            non_empty = 0
            for row in rows:
                residual = normalize_lineup_text(row["lineup_raw"])
                if residual:
                    non_empty += 1

                cursor.execute(
                    """
                    UPDATE events
                    SET lineup_residual_text = %s
                    WHERE id = %s
                    """,
                    (residual, row["id"]),
                )
                updated += 1

        connection.commit()

    print(f"Backfilled {updated} events; {non_empty} have residual lineup text")


if __name__ == "__main__":
    main()
