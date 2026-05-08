import argparse
import json
import os
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


DATABASE_URL = os.environ["DATABASE_URL"]


class ImportValidationError(ValueError):
    pass


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"

    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def require_text(row: dict[str, Any], field: str, context: str) -> str:
    value = row.get(field)
    if value is None or str(value).strip() == "":
        raise ImportValidationError(f"{context}: missing required field '{field}'")
    return str(value)


def nested(row: dict[str, Any], *keys: str) -> Any:
    current: Any = row
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def clean_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: clean_payload(item)
            for key, item in value.items()
            if key != "__typename"
        }
    if isinstance(value, list):
        return [clean_payload(item) for item in value]
    return value


def validate_event(event: dict[str, Any], index: int) -> None:
    context = f"event[{index}]"
    require_text(event, "id", context)
    require_text(event, "title", context)

    venue = event.get("venue")
    if venue is not None:
        if not isinstance(venue, dict):
            raise ImportValidationError(f"{context}: venue must be an object")
        require_text(venue, "id", f"{context}.venue")
        require_text(venue, "name", f"{context}.venue")

    for field in ("artists", "promoters", "genres", "images"):
        items = event.get(field, [])
        if not isinstance(items, list):
            raise ImportValidationError(f"{context}: {field} must be a list")

        for item_index, item in enumerate(items, start=1):
            item_context = f"{context}.{field}[{item_index}]"
            if not isinstance(item, dict):
                raise ImportValidationError(f"{item_context}: item must be an object")
            if field != "images":
                require_text(item, "id", item_context)
                require_text(item, "name", item_context)
            elif item.get("filename") is None and item.get("id") is not None:
                raise ImportValidationError(f"{item_context}: image with id must include filename")


def load_events(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)

    if isinstance(payload, dict):
        payload = payload.get("events", [])

    if not isinstance(payload, list):
        raise ImportValidationError("import file must contain a list or an object with an events list")

    events: list[dict[str, Any]] = []
    for index, event in enumerate(payload, start=1):
        if not isinstance(event, dict):
            raise ImportValidationError(f"event[{index}]: item must be an object")
        validate_event(event, index)
        events.append(event)

    return events


def upsert_venue(cursor: psycopg.Cursor, venue: dict[str, Any] | None) -> int | None:
    if not venue:
        return None

    cursor.execute(
        """
        INSERT INTO venues (
            ra_venue_id, name, content_url, address, latitude, longitude, live, area_name, country_code
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ra_venue_id) DO UPDATE SET
            name = EXCLUDED.name,
            content_url = EXCLUDED.content_url,
            address = EXCLUDED.address,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            live = EXCLUDED.live,
            area_name = EXCLUDED.area_name,
            country_code = EXCLUDED.country_code
        RETURNING id
        """,
        (
            str(venue["id"]),
            venue["name"],
            venue.get("contentUrl"),
            venue.get("address"),
            nested(venue, "location", "latitude"),
            nested(venue, "location", "longitude"),
            venue.get("live"),
            nested(venue, "area", "name"),
            nested(venue, "area", "country", "urlCode"),
        ),
    )
    return cursor.fetchone()["id"]


def upsert_lookup(
    cursor: psycopg.Cursor,
    table: str,
    ra_column: str,
    payload: dict[str, Any],
    fields: Iterable[tuple[str, Any]],
) -> int:
    columns = [ra_column, "name", *[field for field, _ in fields]]
    values = [str(payload["id"]), payload["name"], *[value for _, value in fields]]
    updates = ", ".join(f"{column} = EXCLUDED.{column}" for column in columns[1:])

    cursor.execute(
        f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES ({", ".join(["%s"] * len(columns))})
        ON CONFLICT ({ra_column}) DO UPDATE SET {updates}
        RETURNING id
        """,
        values,
    )
    return cursor.fetchone()["id"]


def link(cursor: psycopg.Cursor, table: str, event_id: int, target_column: str, target_id: int) -> None:
    cursor.execute(
        f"""
        INSERT INTO {table} (event_id, {target_column})
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        """,
        (event_id, target_id),
    )


def import_event(cursor: psycopg.Cursor, event: dict[str, Any]) -> None:
    venue_id = upsert_venue(cursor, event.get("venue"))

    cursor.execute(
        """
        INSERT INTO events (
            ra_event_id, title, description_text, lineup_raw, content_url, event_date,
            start_time, end_time, minimum_age, cost_text, interested_count, is_ticketed,
            is_festival, live, has_secret_venue, date_posted, date_updated, venue_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ra_event_id) DO UPDATE SET
            title = EXCLUDED.title,
            description_text = EXCLUDED.description_text,
            lineup_raw = EXCLUDED.lineup_raw,
            content_url = EXCLUDED.content_url,
            event_date = EXCLUDED.event_date,
            start_time = EXCLUDED.start_time,
            end_time = EXCLUDED.end_time,
            minimum_age = EXCLUDED.minimum_age,
            cost_text = EXCLUDED.cost_text,
            interested_count = EXCLUDED.interested_count,
            is_ticketed = EXCLUDED.is_ticketed,
            is_festival = EXCLUDED.is_festival,
            live = EXCLUDED.live,
            has_secret_venue = EXCLUDED.has_secret_venue,
            date_posted = EXCLUDED.date_posted,
            date_updated = EXCLUDED.date_updated,
            venue_id = EXCLUDED.venue_id
        RETURNING id
        """,
        (
            str(event["id"]),
            event["title"],
            event.get("content"),
            event.get("lineup"),
            event.get("contentUrl"),
            parse_datetime(event.get("date")),
            parse_datetime(event.get("startTime")),
            parse_datetime(event.get("endTime")),
            event.get("minimumAge"),
            event.get("cost"),
            event.get("interestedCount"),
            event.get("isTicketed"),
            event.get("isFestival"),
            event.get("live"),
            event.get("hasSecretVenue"),
            parse_datetime(event.get("datePosted")),
            parse_datetime(event.get("dateUpdated")),
            venue_id,
        ),
    )
    event_id = cursor.fetchone()["id"]

    for artist in event.get("artists", []):
        artist_id = upsert_lookup(
            cursor,
            "artists",
            "ra_artist_id",
            artist,
            (
                ("content_url", artist.get("contentUrl")),
                ("url_safe_name", artist.get("urlSafeName")),
            ),
        )
        link(cursor, "event_artists", event_id, "artist_id", artist_id)

    for genre in event.get("genres", []):
        genre_id = upsert_lookup(
            cursor,
            "genres",
            "ra_genre_id",
            genre,
            (("slug", genre.get("slug")),),
        )
        link(cursor, "event_genres", event_id, "genre_id", genre_id)

    for promoter in event.get("promoters", []):
        promoter_id = upsert_lookup(
            cursor,
            "promoters",
            "ra_promoter_id",
            promoter,
            (
                ("content_url", promoter.get("contentUrl")),
                ("live", promoter.get("live")),
                ("has_ticket_access", promoter.get("hasTicketAccess")),
            ),
        )
        link(cursor, "event_promoters", event_id, "promoter_id", promoter_id)

    for image in event.get("images", []):
        image_url = image.get("filename")
        if not image_url:
            continue

        cursor.execute(
            """
            INSERT INTO event_images (ra_image_id, event_id, image_url, image_type, alt_text)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (ra_image_id) DO UPDATE SET
                event_id = EXCLUDED.event_id,
                image_url = EXCLUDED.image_url,
                image_type = EXCLUDED.image_type,
                alt_text = EXCLUDED.alt_text
            """,
            (
                str(image["id"]) if image.get("id") else None,
                event_id,
                image_url,
                image.get("type"),
                image.get("alt"),
            ),
        )

    cursor.execute(
        """
        INSERT INTO event_source_payloads (event_id, source_name, source_event_id, payload)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (event_id) DO UPDATE SET
            source_name = EXCLUDED.source_name,
            source_event_id = EXCLUDED.source_event_id,
            payload = EXCLUDED.payload,
            fetched_at = CURRENT_TIMESTAMP
        """,
        (event_id, "ra", str(event["id"]), json.dumps(clean_payload(event))),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import RA events JSON into Postgres.")
    parser.add_argument(
        "path",
        nargs="?",
        default=os.environ.get("EVENTS_JSON_PATH", "data/ra_berlin_past_events_2026.json"),
        help="Path to an RA events JSON file. Defaults to EVENTS_JSON_PATH or backend/data/...",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate input without inserting rows.")
    args = parser.parse_args()

    events = load_events(Path(args.path))
    print(f"Validated {len(events)} events from {args.path}")

    if args.dry_run:
        return

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            for index, event in enumerate(events, start=1):
                import_event(cursor, event)
                if index % 100 == 0:
                    print(f"Imported {index}/{len(events)} events")
        connection.commit()

    print(f"Imported {len(events)} events")


if __name__ == "__main__":
    main()
