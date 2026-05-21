import argparse
import os
import sys
from pathlib import Path
from typing import Literal

import psycopg
from psycopg.rows import dict_row

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.text_profiles import normalize_biography_text
from scripts.import_events import normalize_lineup_text


DATABASE_URL = os.environ["DATABASE_URL"]
BackfillTarget = Literal["lineup", "biography"]


def assert_column(connection: psycopg.Connection, table_name: str, column_name: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            """,
            (table_name, column_name),
        )
        if cursor.fetchone() is None:
            raise SystemExit(
                f"{table_name}.{column_name} does not exist. "
                "Run `make prisma-migrate` before backfilling."
            )


def backfill_lineups(connection: psycopg.Connection) -> tuple[int, int]:
    assert_column(connection, "events", "lineup_residual_text")

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
    return updated, non_empty


def backfill_biographies(connection: psycopg.Connection) -> tuple[int, int]:
    assert_column(connection, "artists", "biography_normalized")

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, biography FROM artists WHERE biography IS NOT NULL")
        rows = cursor.fetchall()

        updated = 0
        non_empty = 0
        for row in rows:
            biography_normalized = normalize_biography_text(row["biography"])
            if biography_normalized:
                non_empty += 1

            cursor.execute(
                """
                UPDATE artists
                SET biography_normalized = %s
                WHERE id = %s
                """,
                (biography_normalized, row["id"]),
            )
            updated += 1

    connection.commit()
    return updated, non_empty


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill normalized text fields.")
    parser.add_argument(
        "--target",
        choices=("all", "lineup", "biography"),
        default="all",
        help="Which normalized text field to backfill. Defaults to all.",
    )
    return parser.parse_args()


def selected_targets(selection: str) -> list[BackfillTarget]:
    if selection == "all":
        return ["lineup", "biography"]
    return [selection]  # type: ignore[list-item]


def main() -> None:
    args = parse_args()

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        for target in selected_targets(args.target):
            if target == "lineup":
                updated, non_empty = backfill_lineups(connection)
                print(f"Backfilled {updated} events; {non_empty} have residual lineup text")
            else:
                updated, non_empty = backfill_biographies(connection)
                print(
                    f"Backfilled {updated} artists; "
                    f"{non_empty} have normalized biography text"
                )


if __name__ == "__main__":
    main()
