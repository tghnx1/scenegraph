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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Scenegraph import integrity in Postgres.")
    parser.add_argument("--min-events", type=int, default=1)
    parser.add_argument("--min-artists", type=int, default=1)
    parser.add_argument("--require-embeddings", action="store_true")
    parser.add_argument("--check-artist-id", type=int, default=None)
    parser.add_argument("--biographies-path", default=None)
    parser.add_argument("--event-ids-file", type=Path, default=None)
    parser.add_argument("--artist-ids-file", type=Path, default=None)
    return parser.parse_args()


def fetch_scalar(connection: psycopg.Connection, query: str, params: tuple = ()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()
    if not row:
        return 0
    value = next(iter(row.values()))
    return int(value if value is not None else 0)


def fetch_id_count(
    connection: psycopg.Connection,
    table: str,
    ids: list[int] | None,
    column: str = "id",
) -> int:
    if ids is None:
        return fetch_scalar(connection, f"SELECT COUNT(*) FROM {table}")
    if not ids:
        return 0
    return fetch_scalar(
        connection,
        f"SELECT COUNT(*) FROM {table} WHERE {column} = ANY(%s)",
        (ids,),
    )


def run_checks(connection: psycopg.Connection, args: argparse.Namespace) -> list[CheckResult]:
    results: list[CheckResult] = []
    event_ids = load_id_file(args.event_ids_file)
    artist_ids = load_id_file(args.artist_ids_file)

    if args.biographies_path:
        bio_path = Path(args.biographies_path)
        if not bio_path.exists():
            results.append(CheckResult("biography-file-items", False, f"path={bio_path} missing"))
        else:
            try:
                with bio_path.open("r", encoding="utf-8") as bio_file:
                    payload = json.load(bio_file)
                if isinstance(payload, dict):
                    payload = payload.get("artists", payload.get("items", []))
                if not isinstance(payload, list):
                    raise ValueError("expected JSON list or object with artists/items list")
                results.append(CheckResult("biography-file-items", True, f"path={bio_path}, items={len(payload)}"))
            except Exception as exc:
                results.append(CheckResult("biography-file-items", False, f"path={bio_path}, error={exc}"))

    counts = {
        "events": fetch_id_count(connection, "events", event_ids),
        "artists": fetch_id_count(connection, "artists", artist_ids),
        "event_artists": fetch_id_count(connection, "event_artists", event_ids, "event_id"),
        "event_promoters": fetch_id_count(connection, "event_promoters", event_ids, "event_id"),
        "event_genres": fetch_id_count(connection, "event_genres", event_ids, "event_id"),
        "event_payloads": fetch_id_count(connection, "event_source_payloads", event_ids, "event_id"),
        "entity_embeddings": fetch_scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM entity_embeddings
            WHERE
                (entity_type = 'event' AND (%s::int[] IS NULL OR entity_id = ANY(%s)))
                OR (entity_type = 'artist' AND (%s::int[] IS NULL OR entity_id = ANY(%s)))
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
                f"event_artists={counts['event_artists']}, "
                f"event_promoters={counts['event_promoters']}, "
                f"event_genres={counts['event_genres']}, "
                f"event_payloads={counts['event_payloads']}, "
                f"entity_embeddings={counts['entity_embeddings']}"
            ),
        )
    )

    if event_ids is not None and event_ids:
        results.append(
            CheckResult(
                "events-present",
                counts["events"] == len(set(event_ids)),
                f"expected={len(set(event_ids))}, actual={counts['events']}",
            )
        )
        results.append(
            CheckResult(
                "event-payloads-present",
                counts["event_payloads"] == len(set(event_ids)),
                f"expected={len(set(event_ids))}, actual={counts['event_payloads']}",
            )
        )

    if artist_ids is not None and artist_ids:
        results.append(
            CheckResult(
                "artists-present",
                counts["artists"] == len(set(artist_ids)),
                f"expected={len(set(artist_ids))}, actual={counts['artists']}",
            )
        )

    results.append(
        CheckResult(
            "duplicates-events-ra_event_id",
            fetch_scalar(
                connection,
                """
                SELECT COUNT(*) FROM (
                    SELECT ra_event_id
                    FROM events
                    WHERE (%s::int[] IS NULL OR id = ANY(%s))
                    GROUP BY ra_event_id
                    HAVING COUNT(*) > 1
                ) d
                """,
                (event_ids, event_ids or []),
            )
            == 0,
            "slice-scoped",
        )
    )
    results.append(
        CheckResult(
            "duplicates-artists-ra_artist_id",
            fetch_scalar(
                connection,
                """
                SELECT COUNT(*) FROM (
                    SELECT ra_artist_id
                    FROM artists
                    WHERE (%s::int[] IS NULL OR id = ANY(%s))
                    GROUP BY ra_artist_id
                    HAVING COUNT(*) > 1
                ) d
                """,
                (artist_ids, artist_ids or []),
            )
            == 0,
            "slice-scoped",
        )
    )

    if args.require_embeddings:
        results.append(
            CheckResult(
                "embeddings-required",
                counts["entity_embeddings"] > 0,
                f"entity_embeddings={counts['entity_embeddings']}",
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

    with connection.cursor() as cursor:
        if event_ids is None:
            cursor.execute(
                """
                SELECT MAX(date_updated) AS max_event_updated, MAX(date_posted) AS max_event_posted
                FROM events
                """
            )
            cursor2_query = "SELECT MAX(fetched_at) AS max_payload_fetched FROM event_source_payloads"
            cursor2_params = ()
        elif event_ids:
            cursor.execute(
                """
                SELECT MAX(date_updated) AS max_event_updated, MAX(date_posted) AS max_event_posted
                FROM events
                WHERE id = ANY(%s)
                """,
                (event_ids,),
            )
            cursor2_query = "SELECT MAX(fetched_at) AS max_payload_fetched FROM event_source_payloads WHERE event_id = ANY(%s)"
            cursor2_params = (event_ids,)
        else:
            cursor.execute(
                "SELECT NULL::timestamptz AS max_event_updated, NULL::timestamptz AS max_event_posted"
            )
            cursor2_query = "SELECT NULL::timestamptz AS max_payload_fetched"
            cursor2_params = ()

        events_freshness = cursor.fetchone() or {}
        cursor.execute(cursor2_query, cursor2_params)
        payload_freshness = cursor.fetchone() or {}

    results.append(
        CheckResult(
            "freshness-markers",
            bool(events_freshness.get("max_event_updated") or events_freshness.get("max_event_posted") or payload_freshness.get("max_payload_fetched")),
            (
                f"max_event_updated={events_freshness.get('max_event_updated')}, "
                f"max_event_posted={events_freshness.get('max_event_posted')}, "
                f"max_payload_fetched={payload_freshness.get('max_payload_fetched')}"
            ),
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
