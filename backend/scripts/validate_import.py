import argparse
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
    return parser.parse_args()


def fetch_scalar(connection: psycopg.Connection, query: str, params: tuple = ()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()
    if not row:
        return 0
    value = next(iter(row.values()))
    return int(value if value is not None else 0)


def run_checks(connection: psycopg.Connection, args: argparse.Namespace) -> list[CheckResult]:
    results: list[CheckResult] = []

    counts = {
        "events": fetch_scalar(connection, "SELECT COUNT(*) FROM events"),
        "artists": fetch_scalar(connection, "SELECT COUNT(*) FROM artists"),
        "promoters": fetch_scalar(connection, "SELECT COUNT(*) FROM promoters"),
        "genres": fetch_scalar(connection, "SELECT COUNT(*) FROM genres"),
        "event_artists": fetch_scalar(connection, "SELECT COUNT(*) FROM event_artists"),
        "event_promoters": fetch_scalar(connection, "SELECT COUNT(*) FROM event_promoters"),
        "event_genres": fetch_scalar(connection, "SELECT COUNT(*) FROM event_genres"),
        "entity_embeddings": fetch_scalar(connection, "SELECT COUNT(*) FROM entity_embeddings"),
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
                GROUP BY ra_event_id
                HAVING COUNT(*) > 1
            ) d
        """,
        "duplicates-artists-ra_artist_id": """
            SELECT COUNT(*) FROM (
                SELECT ra_artist_id
                FROM artists
                GROUP BY ra_artist_id
                HAVING COUNT(*) > 1
            ) d
        """,
        "duplicates-promoters-ra_promoter_id": """
            SELECT COUNT(*) FROM (
                SELECT ra_promoter_id
                FROM promoters
                GROUP BY ra_promoter_id
                HAVING COUNT(*) > 1
            ) d
        """,
        "duplicates-genres-ra_genre_id": """
            SELECT COUNT(*) FROM (
                SELECT ra_genre_id
                FROM genres
                GROUP BY ra_genre_id
                HAVING COUNT(*) > 1
            ) d
        """,
        "duplicates-event_artists": """
            SELECT COUNT(*) FROM (
                SELECT event_id, artist_id
                FROM event_artists
                GROUP BY event_id, artist_id
                HAVING COUNT(*) > 1
            ) d
        """,
        "duplicates-event_promoters": """
            SELECT COUNT(*) FROM (
                SELECT event_id, promoter_id
                FROM event_promoters
                GROUP BY event_id, promoter_id
                HAVING COUNT(*) > 1
            ) d
        """,
        "duplicates-event_genres": """
            SELECT COUNT(*) FROM (
                SELECT event_id, genre_id
                FROM event_genres
                GROUP BY event_id, genre_id
                HAVING COUNT(*) > 1
            ) d
        """,
    }
    for name, query in duplicate_checks.items():
        duplicates = fetch_scalar(connection, query)
        results.append(CheckResult(name, duplicates == 0, f"duplicate_groups={duplicates}"))

    orphan_checks = {
        "orphans-event_artists": """
            SELECT COUNT(*)
            FROM event_artists ea
            LEFT JOIN events e ON e.id = ea.event_id
            LEFT JOIN artists a ON a.id = ea.artist_id
            WHERE e.id IS NULL OR a.id IS NULL
        """,
        "orphans-event_promoters": """
            SELECT COUNT(*)
            FROM event_promoters ep
            LEFT JOIN events e ON e.id = ep.event_id
            LEFT JOIN promoters p ON p.id = ep.promoter_id
            WHERE e.id IS NULL OR p.id IS NULL
        """,
        "orphans-event_genres": """
            SELECT COUNT(*)
            FROM event_genres eg
            LEFT JOIN events e ON e.id = eg.event_id
            LEFT JOIN genres g ON g.id = eg.genre_id
            WHERE e.id IS NULL OR g.id IS NULL
        """,
    }
    for name, query in orphan_checks.items():
        orphan_rows = fetch_scalar(connection, query)
        results.append(CheckResult(name, orphan_rows == 0, f"rows={orphan_rows}"))

    null_checks = {
        "nulls-events-required": """
            SELECT COUNT(*) FROM events
            WHERE ra_event_id IS NULL OR title IS NULL
        """,
        "nulls-artists-required": """
            SELECT COUNT(*) FROM artists
            WHERE ra_artist_id IS NULL OR name IS NULL
        """,
        "nulls-promoters-required": """
            SELECT COUNT(*) FROM promoters
            WHERE ra_promoter_id IS NULL OR name IS NULL
        """,
        "nulls-genres-required": """
            SELECT COUNT(*) FROM genres
            WHERE ra_genre_id IS NULL OR name IS NULL
        """,
    }
    for name, query in null_checks.items():
        bad_rows = fetch_scalar(connection, query)
        results.append(CheckResult(name, bad_rows == 0, f"rows={bad_rows}"))

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                MAX(date_updated) AS max_event_updated,
                MAX(date_posted) AS max_event_posted
            FROM events
            """
        )
        events_freshness = cursor.fetchone() or {}
        cursor.execute("SELECT MAX(fetched_at) AS max_payload_fetched FROM event_source_payloads")
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
