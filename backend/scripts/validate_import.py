import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.append(str(Path(__file__).resolve().parents[1]))

DATABASE_URL = os.environ["DATABASE_URL"]


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Scenegraph import integrity in Postgres.")
    parser.add_argument(
        "--min-events",
        type=int,
        default=1,
        help="Minimum number of rows expected in events table. Defaults to 1.",
    )
    parser.add_argument(
        "--min-artists",
        type=int,
        default=1,
        help="Minimum number of rows expected in artists table. Defaults to 1.",
    )
    parser.add_argument(
        "--require-embeddings",
        action="store_true",
        help="Fail if entity_embeddings has 0 rows.",
    )
    parser.add_argument(
        "--check-artist-id",
        type=int,
        default=None,
        help="Optional artist id that must have at least one embedding row.",
    )
    parser.add_argument(
        "--biographies-path",
        default=None,
        help=(
            "Optional path to artist_biographies JSON to validate file presence/format "
            "and report item count."
        ),
    )
    parser.add_argument(
        "--event-ids-file",
        type=Path,
        default=None,
        help="Optional newline-delimited list of imported event ids to validate.",
    )
    parser.add_argument(
        "--artist-ids-file",
        type=Path,
        default=None,
        help="Optional newline-delimited list of imported artist ids to validate.",
    )
    return parser.parse_args()


def fetch_scalar(connection: psycopg.Connection, query: str, params: tuple = ()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()
    if not row:
        return 0
    value = next(iter(row.values()))
    return int(value if value is not None else 0)


def count_from_ids(
    connection: psycopg.Connection,
    *,
    table: str,
    id_column: str = "id",
    ids: list[int] | None,
) -> int:
    if ids is None:
        return fetch_scalar(connection, f"SELECT COUNT(*) FROM {table}")
    if not ids:
        return 0
    return fetch_scalar(
        connection,
        f"SELECT COUNT(*) FROM {table} WHERE {id_column} = ANY(%s)",
        (ids,),
    )


def scoped_where(ids: list[int] | None, column: str) -> tuple[str, tuple]:
    if ids is None:
        return "WHERE TRUE", ()
    if not ids:
        return "WHERE FALSE", ()
    return f"WHERE {column} = ANY(%s)", (ids,)


def run_checks(connection: psycopg.Connection, args: argparse.Namespace) -> list[CheckResult]:
    results: list[CheckResult] = []
    event_ids = load_id_file(args.event_ids_file)
    artist_ids = load_id_file(args.artist_ids_file)

    if args.biographies_path:
        bio_path = Path(args.biographies_path)
        if not bio_path.exists():
            results.append(
                CheckResult(
                    "biography-file-items",
                    False,
                    f"path={bio_path} missing",
                )
            )
        else:
            try:
                with bio_path.open("r", encoding="utf-8") as bio_file:
                    payload = json.load(bio_file)
                if isinstance(payload, dict):
                    payload = payload.get("artists", payload.get("items", []))
                if not isinstance(payload, list):
                    raise ValueError("expected JSON list or object with artists/items list")
                results.append(
                    CheckResult(
                        "biography-file-items",
                        True,
                        f"path={bio_path}, items={len(payload)}",
                    )
                )
            except Exception as exc:
                results.append(
                    CheckResult(
                        "biography-file-items",
                        False,
                        f"path={bio_path}, error={exc}",
                    )
                )

    counts = {
        "events": count_from_ids(connection, table="events", ids=event_ids),
        "artists": count_from_ids(connection, table="artists", ids=artist_ids),
        "promoters": fetch_scalar(
            connection,
            """
            SELECT COUNT(DISTINCT p.id)
            FROM promoters p
            LEFT JOIN event_promoters ep ON ep.promoter_id = p.id
            {event_where}
            """.format(event_where=("WHERE ep.event_id = ANY(%s)" if event_ids is not None else "")),
            (event_ids,) if event_ids is not None else (),
        ),
        "genres": fetch_scalar(
            connection,
            """
            SELECT COUNT(DISTINCT g.id)
            FROM genres g
            LEFT JOIN event_genres eg ON eg.genre_id = g.id
            {event_where}
            """.format(event_where=("WHERE eg.event_id = ANY(%s)" if event_ids is not None else "")),
            (event_ids,) if event_ids is not None else (),
        ),
        "event_artists": count_from_ids(connection, table="event_artists", id_column="event_id", ids=event_ids),
        "event_promoters": count_from_ids(connection, table="event_promoters", id_column="event_id", ids=event_ids),
        "event_genres": count_from_ids(connection, table="event_genres", id_column="event_id", ids=event_ids),
        "entity_embeddings": fetch_scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM entity_embeddings
            WHERE (
                (%s::int[] IS NOT NULL AND entity_type = 'event' AND entity_id = ANY(%s))
                OR (%s::int[] IS NOT NULL AND entity_type = 'artist' AND entity_id = ANY(%s))
            )
            """,
            (event_ids, event_ids or [], artist_ids, artist_ids or []),
        ),
    }
    results.append(
        CheckResult(
            "row-counts",
            counts["events"] >= args.min_events and counts["artists"] >= args.min_artists,
            (
                f"events={counts['events']} (min={args.min_events}), "
                f"artists={counts['artists']} (min={args.min_artists}), "
                f"promoters={counts['promoters']}, genres={counts['genres']}, "
                f"event_artists={counts['event_artists']}, "
                f"event_promoters={counts['event_promoters']}, "
                f"event_genres={counts['event_genres']}, "
                f"entity_embeddings={counts['entity_embeddings']}"
            ),
        )
    )

    duplicate_checks = {
        "duplicates-events-ra_event_id": """
            SELECT COUNT(*) FROM (
                SELECT ra_event_id
                FROM events
                {event_where}
                GROUP BY ra_event_id
                HAVING COUNT(*) > 1
            ) d
        """,
        "duplicates-artists-ra_artist_id": """
            SELECT COUNT(*) FROM (
                SELECT ra_artist_id
                FROM artists
                {artist_where}
                GROUP BY ra_artist_id
                HAVING COUNT(*) > 1
            ) d
        """,
        "duplicates-promoters-ra_promoter_id": """
            SELECT COUNT(*) FROM (
                SELECT ra_promoter_id
                FROM promoters
                {promoter_where}
                GROUP BY ra_promoter_id
                HAVING COUNT(*) > 1
            ) d
        """,
        "duplicates-genres-ra_genre_id": """
            SELECT COUNT(*) FROM (
                SELECT ra_genre_id
                FROM genres
                {genre_where}
                GROUP BY ra_genre_id
                HAVING COUNT(*) > 1
            ) d
        """,
        "duplicates-event_artists": """
            SELECT COUNT(*) FROM (
                SELECT event_id, artist_id
                FROM event_artists
                {event_where}
                GROUP BY event_id, artist_id
                HAVING COUNT(*) > 1
            ) d
        """,
        "duplicates-event_promoters": """
            SELECT COUNT(*) FROM (
                SELECT event_id, promoter_id
                FROM event_promoters
                {event_where}
                GROUP BY event_id, promoter_id
                HAVING COUNT(*) > 1
            ) d
        """,
        "duplicates-event_genres": """
            SELECT COUNT(*) FROM (
                SELECT event_id, genre_id
                FROM event_genres
                {event_where}
                GROUP BY event_id, genre_id
                HAVING COUNT(*) > 1
            ) d
        """,
    }
    for name, query in duplicate_checks.items():
        if name.startswith("duplicates-events"):
            where, params = scoped_where(event_ids, "id")
        elif name.startswith("duplicates-artists"):
            where, params = scoped_where(artist_ids, "id")
        elif name.startswith("duplicates-promoters") or name.startswith("duplicates-genres"):
            where, params = scoped_where(event_ids, "event_id")
        else:
            where, params = scoped_where(event_ids, "event_id")
        duplicates = fetch_scalar(
            connection,
            query.format(
                event_where=where if name.startswith("duplicates-events") or name.startswith("duplicates-event") else "",
                artist_where=where if name.startswith("duplicates-artists") else "",
                promoter_where=where if name.startswith("duplicates-promoters") else "",
                genre_where=where if name.startswith("duplicates-genres") else "",
            ),
            params,
        )
        results.append(CheckResult(name, duplicates == 0, f"duplicate_groups={duplicates}"))

    orphan_checks = {
        "orphans-event_artists": """
            SELECT COUNT(*)
            FROM event_artists ea
            LEFT JOIN events e ON e.id = ea.event_id
            LEFT JOIN artists a ON a.id = ea.artist_id
            {event_where}
            AND (e.id IS NULL OR a.id IS NULL)
        """,
        "orphans-event_promoters": """
            SELECT COUNT(*)
            FROM event_promoters ep
            LEFT JOIN events e ON e.id = ep.event_id
            LEFT JOIN promoters p ON p.id = ep.promoter_id
            {event_where}
            AND (e.id IS NULL OR p.id IS NULL)
        """,
        "orphans-event_genres": """
            SELECT COUNT(*)
            FROM event_genres eg
            LEFT JOIN events e ON e.id = eg.event_id
            LEFT JOIN genres g ON g.id = eg.genre_id
            {event_where}
            AND (e.id IS NULL OR g.id IS NULL)
        """,
    }
    for name, query in orphan_checks.items():
        orphan_rows = fetch_scalar(
            connection,
            query.format(event_where=("WHERE ea.event_id = ANY(%s)" if name == "orphans-event_artists" and event_ids is not None else (
                "WHERE ep.event_id = ANY(%s)" if name == "orphans-event_promoters" and event_ids is not None else (
                    "WHERE eg.event_id = ANY(%s)" if name == "orphans-event_genres" and event_ids is not None else "WHERE 1=1"
                )
            ))),
            (event_ids,) if event_ids is not None else (),
        )
        results.append(CheckResult(name, orphan_rows == 0, f"rows={orphan_rows}"))

    null_checks = {
        "nulls-events-required": """
            SELECT COUNT(*) FROM events
            {event_where}
            AND (ra_event_id IS NULL OR title IS NULL)
        """,
        "nulls-artists-required": """
            SELECT COUNT(*) FROM artists
            {artist_where}
            AND (ra_artist_id IS NULL OR name IS NULL)
        """,
        "nulls-promoters-required": """
            SELECT COUNT(DISTINCT p.id)
            FROM promoters p
            JOIN event_promoters ep ON ep.promoter_id = p.id
            {event_where}
            AND (p.ra_promoter_id IS NULL OR p.name IS NULL)
        """,
        "nulls-genres-required": """
            SELECT COUNT(DISTINCT g.id)
            FROM genres g
            JOIN event_genres eg ON eg.genre_id = g.id
            {event_where}
            AND (g.ra_genre_id IS NULL OR g.name IS NULL)
        """,
    }
    for name, query in null_checks.items():
        if name == "nulls-events-required":
            where, params = scoped_where(event_ids, "id")
        elif name == "nulls-artists-required":
            where, params = scoped_where(artist_ids, "id")
        elif name == "nulls-promoters-required":
            where, params = scoped_where(event_ids, "ep.event_id")
        else:
            where, params = scoped_where(event_ids, "eg.event_id")
        bad_rows = fetch_scalar(
            connection,
            query.format(event_where=where, artist_where=where),
            params,
        )
        results.append(CheckResult(name, bad_rows == 0, f"rows={bad_rows}"))

    with connection.cursor() as cursor:
        if event_ids is None:
            cursor.execute(
                """
                SELECT
                    MAX(date_updated) AS max_event_updated,
                    MAX(date_posted) AS max_event_posted
                FROM events
                """
            )
        elif event_ids:
            cursor.execute(
                """
                SELECT
                    MAX(date_updated) AS max_event_updated,
                    MAX(date_posted) AS max_event_posted
                FROM events
                WHERE id = ANY(%s)
                """,
                (event_ids,),
            )
        else:
            cursor.execute(
                """
                SELECT
                    NULL::timestamptz AS max_event_updated,
                    NULL::timestamptz AS max_event_posted
                """
            )
        events_freshness = cursor.fetchone() or {}
        if event_ids is None:
            cursor.execute("SELECT MAX(fetched_at) AS max_payload_fetched FROM event_source_payloads")
        elif event_ids:
            cursor.execute(
                """
                SELECT MAX(esp.fetched_at) AS max_payload_fetched
                FROM event_source_payloads esp
                WHERE esp.event_id = ANY(%s)
                """,
                (event_ids,),
            )
        else:
            cursor.execute("SELECT NULL::timestamptz AS max_payload_fetched")
        payload_freshness = cursor.fetchone() or {}

    max_event_updated = events_freshness.get("max_event_updated")
    max_event_posted = events_freshness.get("max_event_posted")
    max_payload_fetched = payload_freshness.get("max_payload_fetched")
    freshness_ok = bool(max_event_updated or max_event_posted or max_payload_fetched)
    results.append(
        CheckResult(
            "freshness-markers",
            freshness_ok,
            (
                f"max_event_updated={max_event_updated}, "
                f"max_event_posted={max_event_posted}, "
                f"max_payload_fetched={max_payload_fetched}"
            ),
        )
    )

    if args.require_embeddings:
        embeddings_total = counts["entity_embeddings"]
        results.append(
            CheckResult(
                "embeddings-required",
                embeddings_total > 0,
                f"entity_embeddings={embeddings_total}",
            )
        )

    if args.check_artist_id is not None:
        artist_embedding_rows = fetch_scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM entity_embeddings
            WHERE entity_type = 'artist' AND entity_id = %s
            """,
            (args.check_artist_id,),
        )
        results.append(
            CheckResult(
                "artist-embedding-presence",
                artist_embedding_rows > 0,
                f"artist_id={args.check_artist_id}, rows={artist_embedding_rows}",
            )
        )

    return results


def print_results(results: list[CheckResult]) -> None:
    for result in results:
        status = "OK" if result.ok else "FAIL"
        print(f"[{status}] {result.name}: {result.details}")


def main() -> int:
    args = parse_args()
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        results = run_checks(connection, args)

    print_results(results)
    failed = [result for result in results if not result.ok]
    if failed:
        print(f"\nValidation failed: {len(failed)} check(s) failed.")
        return 1

    print("\nValidation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
