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


def load_id_file(path: Path | None) -> list[int] | None:
    if path is None:
        return None
    if not path.exists():
        raise SystemExit(f"ID file not found: {path}")
    values: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            values.append(int(raw))
        except ValueError as exc:
            raise SystemExit(f"Invalid integer id in {path}: {raw}") from exc
    return values


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


def backfill_lineups(
    connection: psycopg.Connection,
    *,
    event_ids: list[int] | None = None,
    progress_every: int = 1,
) -> tuple[int, int]:
    assert_column(connection, "events", "lineup_residual_text")

    with connection.cursor() as cursor:
        params: list[object] = []
        where = ["lineup_raw IS NOT NULL"]
        if event_ids is not None:
            if not event_ids:
                return 0, 0
            where.append("id = ANY(%s)")
            params.append(event_ids)
        cursor.execute(
            f"SELECT id, lineup_raw, lineup_residual_text FROM events WHERE {' AND '.join(where)} ORDER BY id ASC",
            params,
        )
        rows = cursor.fetchall()

        total = len(rows)
        updated = 0
        non_empty = 0
        for index, row in enumerate(rows, start=1):
            residual = normalize_lineup_text(row["lineup_raw"])
            if residual:
                non_empty += 1

            current = row.get("lineup_residual_text")
            if current == residual:
                if progress_every > 0 and (index == 1 or index == total or index % progress_every == 0):
                    print(f"[lineup] {index}/{total} event_id={row['id']} unchanged", flush=True)
                continue

            cursor.execute(
                """
                UPDATE events
                SET lineup_residual_text = %s
                WHERE id = %s
                """,
                (residual, row["id"]),
            )
            updated += 1
            if progress_every > 0 and (index == 1 or index == total or index % progress_every == 0):
                print(
                    f"[lineup] {index}/{total} event_id={row['id']} updated",
                    flush=True,
                )

    connection.commit()
    return updated, non_empty


def backfill_biographies(
    connection: psycopg.Connection,
    *,
    artist_ids: list[int] | None = None,
    progress_every: int = 1,
) -> tuple[int, int]:
    assert_column(connection, "artists", "biography_normalized")

    with connection.cursor() as cursor:
        params: list[object] = []
        where = ["biography IS NOT NULL"]
        if artist_ids is not None:
            if not artist_ids:
                return 0, 0
            where.append("id = ANY(%s)")
            params.append(artist_ids)
        cursor.execute(
            f"SELECT id, biography, biography_normalized FROM artists WHERE {' AND '.join(where)} ORDER BY id ASC",
            params,
        )
        rows = cursor.fetchall()

        total = len(rows)
        updated = 0
        non_empty = 0
        for index, row in enumerate(rows, start=1):
            biography_normalized = normalize_biography_text(row["biography"])
            if biography_normalized:
                non_empty += 1

            current = row.get("biography_normalized")
            if current == biography_normalized:
                if progress_every > 0 and (index == 1 or index == total or index % progress_every == 0):
                    print(f"[biography] {index}/{total} artist_id={row['id']} unchanged", flush=True)
                continue

            cursor.execute(
                """
                UPDATE artists
                SET biography_normalized = %s
                WHERE id = %s
                """,
                (biography_normalized, row["id"]),
            )
            updated += 1
            if progress_every > 0 and (index == 1 or index == total or index % progress_every == 0):
                print(
                    f"[biography] {index}/{total} artist_id={row['id']} updated",
                    flush=True,
                )

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
    parser.add_argument(
        "--progress-every",
        type=int,
        default=1,
        help="Print progress every N rows. Use 1 for per-row progress.",
    )
    parser.add_argument(
        "--event-ids-file",
        type=Path,
        default=None,
        help="Optional newline-delimited list of event ids to backfill.",
    )
    parser.add_argument(
        "--artist-ids-file",
        type=Path,
        default=None,
        help="Optional newline-delimited list of artist ids to backfill.",
    )
    return parser.parse_args()


def selected_targets(selection: str) -> list[BackfillTarget]:
    if selection == "all":
        return ["lineup", "biography"]
    return [selection]  # type: ignore[list-item]


def main() -> None:
    args = parse_args()
    event_ids = load_id_file(args.event_ids_file)
    artist_ids = load_id_file(args.artist_ids_file)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        for target in selected_targets(args.target):
            if target == "lineup":
                updated, non_empty = backfill_lineups(
                    connection,
                    event_ids=event_ids,
                    progress_every=max(1, args.progress_every),
                )
                print(f"Backfilled {updated} events; {non_empty} have residual lineup text")
            else:
                updated, non_empty = backfill_biographies(
                    connection,
                    artist_ids=artist_ids,
                    progress_every=max(1, args.progress_every),
                )
                print(
                    f"Backfilled {updated} artists; "
                    f"{non_empty} have normalized biography text"
                )


if __name__ == "__main__":
    main()
