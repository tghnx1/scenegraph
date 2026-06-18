from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from psycopg import Connection

from app.event_tag_taxonomy import canonicalize_event_tag
from app.style_tags import canonicalize_style_tags, extract_style_tags, suppress_parent_style_tags


MAX_EVENT_CONTEXTS = 12
MAX_RECURRING_NAMES = 12
MAX_EVENT_DESCRIPTION_CHARS = 3000
MAX_EVENT_LINEUP_CHARS = 2000
MAX_ARTIST_BIOGRAPHY_CHARS = 5000
RA_BIOGRAPHY_PREFIX_RE = re.compile(
    r"^[\s\u0338\u200b\u200c\u200d\u2060\ufeff]*(?:biography\b[:\-\s]*)+",
    re.IGNORECASE,
)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def normalize_biography_text(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""

    text = RA_BIOGRAPHY_PREFIX_RE.sub("", text)
    return normalize_text(text)


def truncate_text(value: Any, max_chars: int) -> str:
    text = normalize_text(value)
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars].rsplit(" ", 1)[0].strip()
    return f"{truncated}..."


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


def format_section(label: str, value: str | Sequence[str], max_chars: int | None = None) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = normalize_text(value)
    else:
        text = ", ".join(unique_texts(value))

    if max_chars is not None:
        text = truncate_text(text, max_chars)

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


def load_event_extracted_genres_by_id(
    connection: Connection,
    event_ids: Iterable[int],
) -> dict[int, list[str]]:
    extracted_tags_by_event_id = load_event_extracted_tags_by_id(
        connection,
        event_ids,
        tag_types=("style", "genre"),
    )
    extracted_genres_by_event_id: dict[int, list[str]] = {}
    for event_id, tag_values_by_type in extracted_tags_by_event_id.items():
        values = tag_values_by_type.get("style", []) + tag_values_by_type.get("genre", [])
        if values:
            extracted_genres_by_event_id[event_id] = unique_texts(values)
    return extracted_genres_by_event_id


def load_event_extracted_tags_by_id(
    connection: Connection,
    event_ids: Iterable[int],
    *,
    tag_types: Iterable[str] | None = None,
) -> dict[int, dict[str, list[str]]]:
    unique_event_ids = sorted({int(event_id) for event_id in event_ids})
    if not unique_event_ids:
        return {}

    requested_tag_types = tuple(
        sorted(
            {
                str(tag_type).strip().lower()
                for tag_type in (tag_types or ("style", "genre", "theme", "mood"))
                if str(tag_type).strip()
            }
        )
    )
    if not requested_tag_types:
        return {}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT event_id, tag_type, tag_value
            FROM event_extracted_tags
            WHERE event_id = ANY(%s)
              AND confidence >= 0.6
              AND tag_type = ANY(%s)
            ORDER BY event_id ASC, tag_type ASC, confidence DESC, tag_value ASC
            """,
            (unique_event_ids, list(requested_tag_types)),
        )
        rows = cursor.fetchall()

    extracted_tags_by_event_id: dict[int, dict[str, list[str]]] = {}
    for row in rows:
        event_id = int(row["event_id"])
        tag_type = str(row["tag_type"]).strip().lower()
        if tag_type not in requested_tag_types:
            continue
        canonical_values = (
            canonicalize_style_tags(row["tag_value"])
            if tag_type in {"style", "genre"}
            else canonicalize_event_tag(tag_type, row["tag_value"])
        )
        if not canonical_values:
            continue
        tag_values_by_type = extracted_tags_by_event_id.setdefault(event_id, {})
        values = tag_values_by_type.setdefault(tag_type, [])
        for canonical in canonical_values:
            if canonical not in values:
                values.append(canonical)
    return extracted_tags_by_event_id


def compose_event_text_profile(
    event: dict[str, Any],
    *,
    artist_names: Iterable[Any] = (),
    promoter_names: Iterable[Any] = (),
    genre_names: Iterable[Any] = (),
    venue_name: str | None = None,
    extracted_genres: Sequence[str] | None = None,
    extracted_tags: dict[str, Sequence[str]] | None = None,
) -> str:
    structured_tag_sections: list[str] = []
    extracted_tags = extracted_tags or {}
    if extracted_tags:
        saved_genres = unique_texts(
            [
                *extracted_tags.get("style", []),
                *extracted_tags.get("genre", []),
            ]
        )
        if saved_genres:
            structured_tag_sections.append(format_section("Extracted genres", saved_genres))
        saved_themes = unique_texts(extracted_tags.get("theme", []))
        if saved_themes:
            structured_tag_sections.append(format_section("Extracted themes", saved_themes))
        saved_moods = unique_texts(extracted_tags.get("mood", []))
        if saved_moods:
            structured_tag_sections.append(format_section("Extracted moods", saved_moods))
    elif extracted_genres:
        structured_tag_sections.append(
            format_section("Extracted genres", suppress_parent_style_tags(unique_texts(extracted_genres)))
        )

    description_section = format_section(
        "Description",
        event.get("description_text", ""),
        MAX_EVENT_DESCRIPTION_CHARS,
    )
    genres_section = format_section("Genres", genre_names)
    venue_section = format_section("Venue", venue_name or event.get("venue_name", ""))
    promoters_section = format_section("Promoters", promoter_names)

    if structured_tag_sections:
        section_order = [
            *structured_tag_sections,
            description_section,
            genres_section,
            venue_section,
            promoters_section,
        ]
    else:
        extracted_genres = extract_style_tags(
            " ".join(
                part
                for part in [
                    normalize_text(event.get("description_text", "")),
                ]
                if part
            )
        )
        section_order = [
            description_section,
            genres_section,
            format_section("Extracted genres", extracted_genres),
            venue_section,
            promoters_section,
        ]

    return join_sections(section_order)


def compose_artist_text_profile(
    artist: dict[str, Any],
    *,
    event_contexts: Iterable[dict[str, Any]] = (),
    venue_names: Iterable[Any] = (),
    promoter_names: Iterable[Any] = (),
    extracted_tags: dict[str, list[str]] | None = None,
) -> str:
    _ = (event_contexts, venue_names, promoter_names)
    extracted_tags = extracted_tags or {}
    biography = artist.get("biography_normalized") or normalize_biography_text(
        artist.get("biography", "")
    )
    stored_style_tags = {
        canonical
        for value in extracted_tags.get("style", [])
        for canonical in canonicalize_style_tags(value)
    }
    style_tags = suppress_parent_style_tags(set(extract_style_tags(biography)) | stored_style_tags)

    return join_sections(
        [
            format_section("Artist name", artist.get("name", "")),
            format_section("Styles", style_tags),
            format_section("Labels", extracted_tags.get("label", [])),
            format_section("Collectives", extracted_tags.get("collective", [])),
            format_section("Roles", extracted_tags.get("role", [])),
            format_section("Residencies", extracted_tags.get("residency", [])),
            format_section(
                "Biography",
                biography,
                MAX_ARTIST_BIOGRAPHY_CHARS,
            ),
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

        cursor.execute(
            """
            SELECT g.name
            FROM genres g
            JOIN event_genres eg
                ON eg.genre_id = g.id
            WHERE eg.event_id = %s
            ORDER BY g.name ASC
            """,
            (event_id,),
        )
        genre_names = [row["name"] for row in cursor.fetchall()]
        extracted_tags_by_event_id = load_event_extracted_tags_by_id(connection, [event_id])

    return compose_event_text_profile(
        event,
        artist_names=artist_names,
        promoter_names=promoter_names,
        genre_names=genre_names,
        venue_name=event["venue_name"],
        extracted_tags=extracted_tags_by_event_id.get(int(event_id), {}),
    )


def build_artist_text_profile(connection: Connection, artist_id: int) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name, biography, biography_normalized
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

        cursor.execute("SELECT to_regclass('public.artist_extracted_tags') AS table_name")
        has_extracted_tags = cursor.fetchone()["table_name"] is not None
        extracted_tags: dict[str, list[str]] = {}
        if has_extracted_tags:
            cursor.execute(
                """
                SELECT tag_type, tag_value
                FROM artist_extracted_tags
                WHERE artist_id = %s
                  AND confidence >= 0.6
                  AND (
                      tag_type <> 'style'
                      OR extractor LIKE 'llm_artist_tags_v2:%%'
                      OR extractor = 'canonical_style_cleanup_v1'
                  )
                ORDER BY tag_type ASC, tag_value ASC
                """,
                (artist_id,),
            )
            for row in cursor.fetchall():
                values = extracted_tags.setdefault(row["tag_type"], [])
                if row["tag_value"] not in values:
                    values.append(row["tag_value"])

    return compose_artist_text_profile(
        artist,
        event_contexts=event_contexts,
        venue_names=venue_names,
        promoter_names=promoter_names,
        extracted_tags=extracted_tags,
    )
