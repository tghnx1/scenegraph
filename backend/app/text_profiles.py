from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from psycopg import Connection


MAX_EVENT_CONTEXTS = 12
MAX_RECURRING_NAMES = 12


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def unique_texts(values: Iterable[Any], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        text = normalize_text(value)
        key = text.lower()
        if not text or key in seen:
            continue

        seen.add(key)
        result.append(text)

        if limit is not None and len(result) >= limit:
            break

    return result


def format_section(label: str, value: str | Sequence[str]) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = normalize_text(value)
    else:
        text = ", ".join(unique_texts(value))

    if not text:
        return ""
    return f"{label}: {text}"


def join_sections(sections: Iterable[str]) -> str:
    return "\n".join(section for section in sections if section)


def rank_recurring_names(values: Iterable[Any], limit: int = MAX_RECURRING_NAMES) -> list[str]:
    normalized = [normalize_text(value) for value in values]
    counts = Counter(text for text in normalized if text)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
    return [name for name, _ in ranked[:limit]]


def compose_event_text_profile(
    event: dict[str, Any],
    *,
    artist_names: Iterable[Any] = (),
    promoter_names: Iterable[Any] = (),
    venue_name: str | None = None,
) -> str:
    return join_sections(
        [
            format_section("Event title", event.get("title", "")),
            format_section("Description", event.get("description_text", "")),
            format_section("Structured lineup", artist_names),
            format_section(
                "Lineup context",
                event.get("lineup_residual_text") or event.get("lineup_raw", ""),
            ),
            format_section("Venue", venue_name or event.get("venue_name", "")),
            format_section("Promoters", promoter_names),
        ]
    )


def compose_artist_text_profile(
    artist: dict[str, Any],
    *,
    event_contexts: Iterable[dict[str, Any]] = (),
    venue_names: Iterable[Any] = (),
    promoter_names: Iterable[Any] = (),
) -> str:
    events = list(event_contexts)
    event_titles = unique_texts((event.get("title") for event in events), MAX_EVENT_CONTEXTS)
    event_descriptions = unique_texts(
        (event.get("description_text") for event in events),
        MAX_EVENT_CONTEXTS,
    )
    event_lineups = unique_texts(
        (event.get("lineup_residual_text") or event.get("lineup_raw") for event in events),
        MAX_EVENT_CONTEXTS,
    )

    return join_sections(
        [
            format_section("Artist name", artist.get("name", "")),
            format_section("Biography", artist.get("biography", "")),
            format_section("Played event titles", event_titles),
            format_section("Played event descriptions", event_descriptions),
            format_section("Played event lineup context", event_lineups),
            format_section("Recurring venues", rank_recurring_names(venue_names)),
            format_section("Recurring promoters", rank_recurring_names(promoter_names)),
        ]
    )


def build_event_text_profile(connection: Connection, event_id: int) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                e.id,
                e.title,
                e.description_text,
                e.lineup_raw,
                e.lineup_residual_text,
                v.name AS venue_name
            FROM events e
            LEFT JOIN venues v
                ON v.id = e.venue_id
            WHERE e.id = %s
            """,
            (event_id,),
        )
        event = cursor.fetchone()

        if event is None:
            raise LookupError(f"Event {event_id} not found")

        cursor.execute(
            """
            SELECT a.name
            FROM artists a
            JOIN event_artists ea
                ON ea.artist_id = a.id
            WHERE ea.event_id = %s
            ORDER BY a.name ASC
            """,
            (event_id,),
        )
        artist_names = [row["name"] for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT p.name
            FROM promoters p
            JOIN event_promoters ep
                ON ep.promoter_id = p.id
            WHERE ep.event_id = %s
            ORDER BY p.name ASC
            """,
            (event_id,),
        )
        promoter_names = [row["name"] for row in cursor.fetchall()]

    return compose_event_text_profile(
        event,
        artist_names=artist_names,
        promoter_names=promoter_names,
        venue_name=event["venue_name"],
    )


def build_artist_text_profile(connection: Connection, artist_id: int) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name, biography
            FROM artists
            WHERE id = %s
            """,
            (artist_id,),
        )
        artist = cursor.fetchone()

        if artist is None:
            raise LookupError(f"Artist {artist_id} not found")

        cursor.execute(
            """
            SELECT
                e.id,
                e.title,
                e.description_text,
                e.lineup_raw,
                e.lineup_residual_text,
                e.event_date,
                v.name AS venue_name
            FROM events e
            JOIN event_artists ea
                ON ea.event_id = e.id
            LEFT JOIN venues v
                ON v.id = e.venue_id
            WHERE ea.artist_id = %s
            ORDER BY e.event_date DESC NULLS LAST, e.id DESC
            LIMIT %s
            """,
            (artist_id, MAX_EVENT_CONTEXTS),
        )
        event_contexts = cursor.fetchall()

        cursor.execute(
            """
            SELECT v.name
            FROM venues v
            JOIN events e
                ON e.venue_id = v.id
            JOIN event_artists ea
                ON ea.event_id = e.id
            WHERE ea.artist_id = %s
            """,
            (artist_id,),
        )
        venue_names = [row["name"] for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT p.name
            FROM promoters p
            JOIN event_promoters ep
                ON ep.promoter_id = p.id
            JOIN event_artists ea
                ON ea.event_id = ep.event_id
            WHERE ea.artist_id = %s
            """,
            (artist_id,),
        )
        promoter_names = [row["name"] for row in cursor.fetchall()]

    return compose_artist_text_profile(
        artist,
        event_contexts=event_contexts,
        venue_names=venue_names,
        promoter_names=promoter_names,
    )
