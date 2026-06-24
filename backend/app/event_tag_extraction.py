from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from openai import AzureOpenAI, OpenAI
from psycopg import Connection

from app.artist_tag_extraction import (
    create_chat_completion,
    create_extraction_client,
    create_azure_responses_completion,
    extract_json_object,
    extract_responses_output_text,
    is_content_filter_error,
    split_biography_chunks,
)
from app.event_style_tags import extract_event_style_matches
from app.event_tag_taxonomy import (
    EVENT_TAG_TYPE_PRIORITY,
    PER_TYPE_LIMITS,
    canonicalize_event_tag,
    evidence_supports_event_tag,
    event_extraction_rules,
    extract_deterministic_event_taxonomy_matches,
    is_event_level_theme_evidence,
    normalize_event_taxonomy_text,
)
from app.text_profiles import normalize_text, truncate_text


ExtractionProvider = Literal["openai", "azure"]
ExtractionApi = Literal["chat_completions", "responses"]
EventTagType = Literal["style", "mood", "theme"]

DEFAULT_EXTRACTION_MODEL = "gpt-4.1-mini"
MAX_EVENT_TEXT_CHARS = 7000
MAX_TAGS_PER_EVENT = 12
CHUNK_FALLBACK_CHARS = 800

ALLOWED_EVENT_TAG_TYPES: set[str] = {
    "mood",
    "theme",
}


@dataclass(frozen=True)
class EventTag:
    tag_type: EventTagType
    tag_value: str
    confidence: float
    evidence: str | None = None


@dataclass(frozen=True)
class EventSourceFields:
    title: str = ""
    description: str = ""
    lineup_text: str = ""
    structured_genres: tuple[str, ...] = ()
    artist_names: tuple[str, ...] = ()
    repeated_title_root: str = ""

    @property
    def text(self) -> str:
        return "\n\n".join(
            value for value in (self.description, self.lineup_text) if value
        )

    @property
    def evidence_text(self) -> str:
        return "\n\n".join(value for value in (self.title, self.text) if value)


@dataclass(frozen=True)
class ChunkedEventTagExtractionResult:
    tags: list[EventTag]
    total_chunks: int
    processed_chunks: int
    skipped_chunks: int


@dataclass(frozen=True)
class EventTagExtractionConfig:
    provider: ExtractionProvider = "openai"
    model: str = DEFAULT_EXTRACTION_MODEL
    api: ExtractionApi = "chat_completions"
    azure_responses_url: str | None = None
    max_text_chars: int = MAX_EVENT_TEXT_CHARS
    max_tags: int = MAX_TAGS_PER_EVENT
    chunk_chars: int = CHUNK_FALLBACK_CHARS

    @classmethod
    def from_env(cls) -> "EventTagExtractionConfig":
        provider = os.environ.get("EXTRACTION_PROVIDER", "openai").strip().lower() or "openai"
        if provider not in {"openai", "azure"}:
            raise ValueError("EXTRACTION_PROVIDER must be either 'openai' or 'azure'")

        azure_responses_url = os.environ.get("AZURE_OPENAI_RESPONSES_URL", "").strip()
        api = os.environ.get("EXTRACTION_API", "").strip().lower()
        if not api:
            api = "responses" if provider == "azure" and azure_responses_url else "chat_completions"
        if api not in {"chat_completions", "responses"}:
            raise ValueError("EXTRACTION_API must be either 'chat_completions' or 'responses'")

        if provider == "azure":
            model = (
                os.environ.get("AZURE_OPENAI_EXTRACTION_DEPLOYMENT", "").strip()
                or os.environ.get("AZURE_OPENAI_RESPONSES_MODEL", "").strip()
                or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "").strip()
                or os.environ.get("OPENAI_EXTRACTION_MODEL", "").strip()
            )
            if not model:
                raise ValueError(
                    "AZURE_OPENAI_EXTRACTION_DEPLOYMENT or AZURE_OPENAI_RESPONSES_MODEL "
                    "must be set when EXTRACTION_PROVIDER=azure"
                )
        else:
            model = os.environ.get("OPENAI_EXTRACTION_MODEL", DEFAULT_EXTRACTION_MODEL).strip()
            if not model:
                model = DEFAULT_EXTRACTION_MODEL

        return cls(
            provider=provider,  # type: ignore[arg-type]
            model=model,
            api=api,  # type: ignore[arg-type]
            azure_responses_url=azure_responses_url or None,
            max_text_chars=int(os.environ.get("EVENT_TAG_EXTRACTION_MAX_TEXT_CHARS", MAX_EVENT_TEXT_CHARS)),
            max_tags=min(
                int(os.environ.get("EVENT_TAG_EXTRACTION_MAX_TAGS", MAX_TAGS_PER_EVENT)),
                MAX_TAGS_PER_EVENT,
            ),
            chunk_chars=int(os.environ.get("EVENT_TAG_EXTRACTION_CHUNK_CHARS", CHUNK_FALLBACK_CHARS)),
        )

    @property
    def extractor_key(self) -> str:
        return f"llm_event_tags_v3:{self.provider}:{self.api}:{self.model}"


def event_tag_extraction_text_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def event_system_prompt() -> str:
    return (
        "You extract structured music-scene facts from event metadata. "
        "Return only JSON. Extract only facts clearly present in the provided event data. "
        "Do not guess. Do not extract musical styles or genres."
    )


def event_user_prompt(event_name: str, event_text: str, max_tags: int) -> str:
    return f"""
Event title: {event_name}

Event text:
{event_text}

Return JSON in this exact shape:
{{
  "tags": [
    {{
      "type": "mood|theme",
      "value": "short normalized tag",
      "confidence": 0.0,
      "evidence": "short phrase from event text"
    }}
  ]
}}

Extraction rules:
{event_extraction_rules()}
- Keep at most {max_tags} tags total.
""".strip()


def event_batch_user_prompt(events: list[dict[str, Any]], max_tags: int) -> str:
    event_blocks = []
    for event in events:
        event_blocks.append(
            f"""
Event ID: {event["id"]}
Event title: {event["name"]}

Event text:
{event["text"]}
""".strip()
        )
    event_text = "\n\n---\n\n".join(event_blocks)
    return f"""
Events:

{event_text}

Return JSON in this exact shape:
{{
  "events": [
    {{
      "eventId": 123,
      "tags": [
        {{
          "type": "mood|theme",
          "value": "short normalized tag",
          "confidence": 0.0,
          "evidence": "short phrase from that event text"
        }}
      ]
    }}
  ]
}}

Extraction rules:
- Extract tags independently for each event ID.
{event_extraction_rules()}
- Keep at most {max_tags} tags per event.
""".strip()


def normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.7
    return max(0.0, min(confidence, 1.0))


def normalized_evidence_is_supported(evidence: str, event_text: str) -> bool:
    normalized_evidence = re.sub(r"[^\w+&-]+", " ", normalize_text(evidence).casefold()).strip()
    normalized_event_text = re.sub(
        r"[^\w+&-]+", " ", normalize_text(event_text).casefold()
    ).strip()
    return bool(normalized_evidence and normalized_evidence in normalized_event_text)


def parse_event_tags_response(
    payload: dict[str, Any],
    *,
    max_tags: int,
    event_title: str = "",
    event_text: str = "",
) -> list[EventTag]:
    raw_tags = payload.get("tags", [])
    if not isinstance(raw_tags, list):
        return []

    tags: list[EventTag] = []
    for item in raw_tags:
        if not isinstance(item, dict):
            continue
        tag_type = normalize_text(item.get("type")).lower()
        if tag_type not in ALLOWED_EVENT_TAG_TYPES:
            continue
        evidence = truncate_text(item.get("evidence", ""), 300) or None
        if evidence is None or not normalized_evidence_is_supported(
            evidence, "\n".join((event_title, event_text))
        ):
            continue
        if tag_type == "theme":
            if not is_event_level_theme_evidence(
                evidence,
                "\n".join((event_title, event_text)),
            ):
                continue
            canonical_values = list(
                dict.fromkeys(
                    canonicalize_event_tag(tag_type, item.get("value"))
                    + canonicalize_event_tag(tag_type, evidence)
                )
            )
        else:
            canonical_values = canonicalize_event_tag(tag_type, item.get("value"))
        for tag_value in canonical_values:
            if not evidence_supports_event_tag(
                tag_type,
                raw_value=item.get("value"),
                canonical_value=tag_value,
                evidence=evidence,
            ):
                continue
            tags.append(
                EventTag(
                    tag_type=tag_type,  # type: ignore[arg-type]
                    tag_value=tag_value,
                    confidence=normalize_confidence(item.get("confidence")),
                    evidence=evidence,
                )
            )
    return finalize_event_tags(tags, max_tags=max_tags)


def _event_tag_priority(tag: EventTag) -> tuple[int, int, float, int, str]:
    type_priority = EVENT_TAG_TYPE_PRIORITY.index(tag.tag_type)
    structured_style_priority = (
        0 if tag.tag_type == "style" and (tag.evidence or "").startswith("structured_genre:") else 1
    )
    return (
        type_priority,
        structured_style_priority,
        -tag.confidence,
        0 if tag.evidence else 1,
        tag.tag_value,
    )


def finalize_event_tags(tags: list[EventTag], *, max_tags: int) -> list[EventTag]:
    merged: dict[tuple[str, str], EventTag] = {}
    for tag in tags:
        key = (tag.tag_type, tag.tag_value.casefold())
        existing = merged.get(key)
        if existing is None or _event_tag_priority(tag) < _event_tag_priority(existing):
            merged[key] = tag

    retained: list[EventTag] = []
    type_counts: dict[str, int] = {}
    for tag in sorted(merged.values(), key=_event_tag_priority):
        if type_counts.get(tag.tag_type, 0) >= PER_TYPE_LIMITS[tag.tag_type]:
            continue
        retained.append(tag)
        type_counts[tag.tag_type] = type_counts.get(tag.tag_type, 0) + 1
    return retained[: min(max_tags, MAX_TAGS_PER_EVENT)]


def merge_event_tags(tag_groups: list[list[EventTag]], *, max_tags: int) -> list[EventTag]:
    return finalize_event_tags(
        [tag for tags in tag_groups for tag in tags],
        max_tags=max_tags,
    )


def canonical_event_style_tags(
    event_text: Any = "",
    *,
    sources: EventSourceFields | None = None,
) -> list[EventTag]:
    sources = sources or EventSourceFields(description=normalize_text(event_text))
    return [
        EventTag(
            tag_type="style",
            tag_value=match.value,
            confidence=match.confidence,
            evidence=f"{match.source}: {match.evidence}",
        )
        for match in extract_event_style_matches(
            title=sources.title,
            description=sources.description,
            lineup_text=sources.lineup_text,
            structured_genres=sources.structured_genres,
            artist_names=sources.artist_names,
        )
    ]


def canonical_event_metadata_tags(
    *,
    sources: EventSourceFields,
) -> list[EventTag]:
    return [
        EventTag(
            tag_type=match.tag_type,  # type: ignore[arg-type]
            tag_value=match.value,
            confidence=match.confidence,
            evidence=f"{match.source}: {match.evidence}",
        )
        for match in extract_deterministic_event_taxonomy_matches(
            title=sources.title,
            description=sources.description,
            lineup_text=sources.lineup_text,
        )
    ]


def merge_event_styles_and_metadata(
    event_text: Any,
    metadata_tags: list[EventTag],
    *,
    max_tags: int,
    sources: EventSourceFields | None = None,
) -> list[EventTag]:
    sources = sources or EventSourceFields(description=normalize_text(event_text))
    return merge_event_tags(
        [
            canonical_event_style_tags(event_text, sources=sources),
            canonical_event_metadata_tags(sources=sources),
            metadata_tags,
        ],
        max_tags=max_tags,
    )


def parse_event_batch_response(
    payload: dict[str, Any], *, events: list[dict[str, Any]], max_tags: int
) -> dict[int, list[EventTag]]:
    raw_events = payload.get("events", [])
    if not isinstance(raw_events, list):
        return {}
    event_ids = {int(event["id"]) for event in events}
    results: dict[int, list[EventTag]] = {}
    for item in raw_events:
        if not isinstance(item, dict):
            continue
        raw_event_id = item.get("eventId", item.get("event_id", item.get("id")))
        try:
            event_id = int(raw_event_id)
        except (TypeError, ValueError):
            continue
        if event_id not in event_ids:
            continue
        event = next(event for event in events if int(event["id"]) == event_id)
        results[event_id] = parse_event_tags_response(
            {"tags": item.get("tags", [])},
            max_tags=max_tags,
            event_title=event["name"],
            event_text=event["text"],
        )
    return results


def event_source_fields(event: dict[str, Any]) -> EventSourceFields:
    return EventSourceFields(
        title=normalize_text(event.get("title") or event.get("name")),
        description=normalize_text(event.get("description_text")),
        lineup_text=normalize_text(
            event.get("lineup_residual_text")
        ),
        structured_genres=tuple(
            normalize_text(value)
            for value in (event.get("structured_genres") or [])
            if normalize_text(value)
        ),
        artist_names=tuple(
            normalize_text(value)
            for value in (event.get("artist_names") or [])
            if normalize_text(value)
        ),
        repeated_title_root=normalize_text(event.get("repeated_title_root")),
    )


def event_extraction_hash_input(event: dict[str, Any]) -> str:
    sources = event_source_fields(event)
    return "\n\n".join(
        value
        for value in (
            sources.title,
            sources.description,
            sources.lineup_text,
            "Structured genres: " + ", ".join(sources.structured_genres)
            if sources.structured_genres
            else "",
            "Known artists: " + ", ".join(sources.artist_names) if sources.artist_names else "",
            "Repeated title root: " + sources.repeated_title_root
            if sources.repeated_title_root
            else "",
        )
        if value
    )


def extract_event_tags_with_llm(
    client: OpenAI | AzureOpenAI | None,
    *,
    event_name: str,
    event_text: str,
    config: EventTagExtractionConfig,
    sources: EventSourceFields | None = None,
) -> list[EventTag]:
    normalized_text = truncate_text(normalize_text(event_text), config.max_text_chars)
    if not normalized_text:
        return merge_event_styles_and_metadata(
            "",
            [],
            max_tags=config.max_tags,
            sources=sources or EventSourceFields(title=event_name),
        )

    prompt = event_user_prompt(event_name, normalized_text, config.max_tags)
    if config.provider == "azure" and config.api == "responses":
        content = create_azure_responses_completion(
            prompt=prompt,
            config=config,  # type: ignore[arg-type]
            instructions=event_system_prompt(),
        )
    else:
        content = create_chat_completion(
            client,
            prompt=prompt,
            config=config,  # type: ignore[arg-type]
            instructions=event_system_prompt(),
        )
    payload = extract_json_object(content)
    return merge_event_styles_and_metadata(
        normalized_text,
        parse_event_tags_response(
            payload,
            max_tags=config.max_tags,
            event_title=event_name,
            event_text=normalized_text,
        ),
        max_tags=config.max_tags,
        sources=sources or EventSourceFields(title=event_name, description=normalized_text),
    )


def extract_event_tags_with_chunked_fallback(
    client: OpenAI | AzureOpenAI | None,
    *,
    event_name: str,
    event_text: str,
    config: EventTagExtractionConfig,
    sources: EventSourceFields | None = None,
) -> ChunkedEventTagExtractionResult:
    chunks = split_biography_chunks(event_text, max_chars=config.chunk_chars)
    tag_groups: list[list[EventTag]] = []
    skipped_chunks = 0
    for chunk in chunks:
        try:
            tag_groups.append(
                extract_event_tags_with_llm(
                    client,
                    event_name=event_name,
                    event_text=chunk,
                    config=config,
                )
            )
        except Exception as exc:
            if not is_content_filter_error(exc):
                raise
            skipped_chunks += 1

    processed_chunks = len(chunks) - skipped_chunks
    merged = merge_event_tags(tag_groups, max_tags=config.max_tags)
    if sources is not None:
        merged = merge_event_styles_and_metadata(
            sources.text,
            [tag for tag in merged if tag.tag_type != "style"],
            max_tags=config.max_tags,
            sources=sources,
        )
    return ChunkedEventTagExtractionResult(
        tags=merged,
        total_chunks=len(chunks),
        processed_chunks=processed_chunks,
        skipped_chunks=skipped_chunks,
    )


def extract_event_tag_batch_with_llm(
    client: OpenAI | AzureOpenAI | None,
    *,
    events: list[dict[str, Any]],
    config: EventTagExtractionConfig,
) -> dict[int, list[EventTag]]:
    prepared_events = []
    for event in events:
        normalized_text = truncate_text(normalize_text(event["text"]), config.max_text_chars)
        if not normalized_text:
            continue
        prepared_events.append({**event, "text": normalized_text})
    if not prepared_events:
        return {}

    prompt = event_batch_user_prompt(prepared_events, config.max_tags)
    if config.provider == "azure" and config.api == "responses":
        content = create_azure_responses_completion(
            prompt=prompt,
            config=config,  # type: ignore[arg-type]
            instructions=event_system_prompt(),
        )
    else:
        content = create_chat_completion(
            client,
            prompt=prompt,
            config=config,  # type: ignore[arg-type]
            instructions=event_system_prompt(),
        )

    payload = extract_json_object(content)
    parsed = parse_event_batch_response(payload, events=prepared_events, max_tags=config.max_tags)
    return {
        int(event["id"]): merge_event_styles_and_metadata(
            event["text"],
            parsed.get(int(event["id"]), []),
            max_tags=config.max_tags,
            sources=event_source_fields(event),
        )
        for event in prepared_events
    }


def fetch_event_texts(
    connection: Connection,
    *,
    event_ids: list[int] | None = None,
    event_id: int | None = None,
    limit: int | None = None,
    offset: int = 0,
    after_id: int | None = None,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = [
        "COALESCE(NULLIF(BTRIM(e.title), ''), NULLIF(BTRIM(e.description_text), ''), NULL) IS NOT NULL"
    ]
    if event_ids is not None:
        if not event_ids:
            return []
        where.append("e.ra_event_id = ANY(%s)")
        params.append([str(event_id) for event_id in event_ids])
    if event_id is not None:
        where.append("e.id = %s")
        params.append(event_id)
    if after_id is not None:
        where.append("e.id > %s")
        params.append(after_id)
    sql = f"""
        SELECT
            e.id,
            e.title AS name,
            e.title,
            e.description_text,
            e.lineup_residual_text,
            e.lineup_raw,
            COALESCE(
                (
                    SELECT array_agg(DISTINCT a.name)
                    FROM event_artists ea
                    JOIN artists a ON a.id = ea.artist_id
                    WHERE ea.event_id = e.id
                      AND a.name IS NOT NULL
                ),
                ARRAY[]::text[]
            ) AS artist_names,
            COALESCE(
                array_agg(DISTINCT g.name) FILTER (WHERE g.name IS NOT NULL),
                ARRAY[]::text[]
            ) AS structured_genres,
            CONCAT_WS(
                '\n\n',
                NULLIF(BTRIM(e.description_text), ''),
                NULLIF(BTRIM(e.lineup_residual_text), ''),
                NULLIF(BTRIM(e.lineup_raw), '')
            ) AS text
        FROM events e
        LEFT JOIN event_genres eg ON eg.event_id = e.id
        LEFT JOIN genres g ON g.id = eg.genre_id
        WHERE {' AND '.join(where)}
        GROUP BY e.id, e.title, e.description_text, e.lineup_residual_text, e.lineup_raw
        ORDER BY e.id ASC
    """
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
    if offset:
        sql += " OFFSET %s"
        params.append(offset)
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        events = cursor.fetchall()
    return events


def has_current_event_tag_extraction(
    connection: Connection,
    *,
    event_id: int,
    source: str,
    extractor: str,
    text_hash: str,
) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM event_tag_extraction_runs
            WHERE event_id = %s
              AND source = %s
              AND extractor = %s
              AND text_hash = %s
            LIMIT 1
            """,
            (event_id, source, extractor, text_hash),
        )
        return cursor.fetchone() is not None


def replace_event_tags(
    connection: Connection,
    *,
    event_id: int,
    source: str,
    extractor: str,
    text_hash: str,
    tags: list[EventTag],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM event_extracted_tags
            WHERE event_id = %s
              AND source = %s
              AND extractor = %s
            """,
            (event_id, source, extractor),
        )
        for tag in tags:
            cursor.execute(
                """
                INSERT INTO event_extracted_tags (
                    event_id, tag_type, tag_value, source, confidence, extractor, evidence
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event_id,
                    tag.tag_type,
                    tag.tag_value,
                    source,
                    tag.confidence,
                    extractor,
                    tag.evidence,
                ),
            )
        cursor.execute(
            """
            INSERT INTO event_tag_extraction_runs (
                event_id, source, extractor, text_hash, tag_count
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (event_id, source, extractor) DO UPDATE SET
                text_hash = EXCLUDED.text_hash,
                tag_count = EXCLUDED.tag_count,
                updated_at = CURRENT_TIMESTAMP
            """,
            (event_id, source, extractor, text_hash, len(tags)),
        )
