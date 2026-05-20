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
from app.text_profiles import normalize_text, truncate_text


ExtractionProvider = Literal["openai", "azure"]
ExtractionApi = Literal["chat_completions", "responses"]
EventTagType = Literal["style", "format", "mood", "theme", "instrumentation", "series"]

DEFAULT_EXTRACTION_MODEL = "gpt-4.1-mini"
MAX_EVENT_TEXT_CHARS = 7000
MAX_TAGS_PER_EVENT = 28
CHUNK_FALLBACK_CHARS = 800

ALLOWED_EVENT_TAG_TYPES: set[str] = {
    "style",
    "format",
    "mood",
    "theme",
    "instrumentation",
    "series",
}


@dataclass(frozen=True)
class EventTag:
    tag_type: EventTagType
    tag_value: str
    confidence: float
    evidence: str | None = None


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
            max_tags=int(os.environ.get("EVENT_TAG_EXTRACTION_MAX_TAGS", MAX_TAGS_PER_EVENT)),
            chunk_chars=int(os.environ.get("EVENT_TAG_EXTRACTION_CHUNK_CHARS", CHUNK_FALLBACK_CHARS)),
        )

    @property
    def extractor_key(self) -> str:
        return f"llm_event_tags_v1:{self.provider}:{self.api}:{self.model}"


def event_tag_extraction_text_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def event_system_prompt() -> str:
    return (
        "You extract structured music-scene facts from event metadata. "
        "Return only JSON. Extract only facts clearly present in the provided event data. "
        "Do not guess."
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
      "type": "style|format|mood|theme|instrumentation|series",
      "value": "short normalized tag",
      "confidence": 0.0,
      "evidence": "short phrase from event text"
    }}
  ]
}}

Extraction rules:
- style: sonic descriptors and genre-like terms from description/lineup context.
- format: event format terms such as DJ set, live set, hybrid live+DJ, b2b, showcase, release party.
- mood: adjectives that describe vibe/atmosphere (e.g. hypnotic, dark, playful, high-energy).
- theme: conceptual framing terms (e.g. queer, feminist, community, fundraiser, ambient-focus).
- instrumentation: explicit instrument or setup mentions (e.g. modular, drum machines, vocals, hardware live).
- series: recurring night/series/franchise names tied to the event.
- Keep at most {max_tags} tags total.
- Prefer fewer high-confidence tags over many weak tags.
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
          "type": "style|format|mood|theme|instrumentation|series",
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
- Keep at most {max_tags} tags per event.
- Prefer fewer high-confidence tags over many weak tags.
""".strip()


def normalize_event_tag_value(tag_type: str, value: Any) -> str:
    text = normalize_text(value).strip(" \t\n\r,.;:|/\\")
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).lower()
    return text[:120].strip()


def normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.7
    return max(0.0, min(confidence, 1.0))


def parse_event_tags_response(payload: dict[str, Any], *, max_tags: int) -> list[EventTag]:
    raw_tags = payload.get("tags", [])
    if not isinstance(raw_tags, list):
        return []

    seen: set[tuple[str, str]] = set()
    tags: list[EventTag] = []
    for item in raw_tags:
        if not isinstance(item, dict):
            continue
        tag_type = normalize_text(item.get("type")).lower()
        if tag_type not in ALLOWED_EVENT_TAG_TYPES:
            continue
        tag_value = normalize_event_tag_value(tag_type, item.get("value"))
        if len(tag_value) < 2:
            continue
        key = (tag_type, tag_value.casefold())
        if key in seen:
            continue

        tags.append(
            EventTag(
                tag_type=tag_type,  # type: ignore[arg-type]
                tag_value=tag_value,
                confidence=normalize_confidence(item.get("confidence")),
                evidence=truncate_text(item.get("evidence", ""), 300) or None,
            )
        )
        seen.add(key)
        if len(tags) >= max_tags:
            break
    return tags


def merge_event_tags(tag_groups: list[list[EventTag]], *, max_tags: int) -> list[EventTag]:
    merged: dict[tuple[str, str], EventTag] = {}
    order: list[tuple[str, str]] = []
    for tags in tag_groups:
        for tag in tags:
            key = (tag.tag_type, tag.tag_value.casefold())
            existing = merged.get(key)
            if existing is None:
                order.append(key)
                merged[key] = tag
            elif tag.confidence > existing.confidence:
                merged[key] = tag
    return [merged[key] for key in order[:max_tags]]


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
        results[event_id] = parse_event_tags_response({"tags": item.get("tags", [])}, max_tags=max_tags)
    return results


def extract_event_tags_with_llm(
    client: OpenAI | AzureOpenAI | None,
    *,
    event_name: str,
    event_text: str,
    config: EventTagExtractionConfig,
) -> list[EventTag]:
    normalized_text = truncate_text(normalize_text(event_text), config.max_text_chars)
    if not normalized_text:
        return []

    prompt = event_user_prompt(event_name, normalized_text, config.max_tags)
    if config.provider == "azure" and config.api == "responses":
        content = create_azure_responses_completion(prompt=prompt, config=config)  # type: ignore[arg-type]
    else:
        content = create_chat_completion(client, prompt=prompt, config=config)  # type: ignore[arg-type]
    payload = extract_json_object(content)
    return parse_event_tags_response(payload, max_tags=config.max_tags)


def extract_event_tags_with_chunked_fallback(
    client: OpenAI | AzureOpenAI | None,
    *,
    event_name: str,
    event_text: str,
    config: EventTagExtractionConfig,
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
    return ChunkedEventTagExtractionResult(
        tags=merge_event_tags(tag_groups, max_tags=config.max_tags),
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
        prepared_events.append({"id": event["id"], "name": event["name"], "text": normalized_text})
    if not prepared_events:
        return {}

    prompt = event_batch_user_prompt(prepared_events, config.max_tags)
    if config.provider == "azure" and config.api == "responses":
        content = create_azure_responses_completion(prompt=prompt, config=config)  # type: ignore[arg-type]
    else:
        content = create_chat_completion(client, prompt=prompt, config=config)  # type: ignore[arg-type]

    payload = extract_json_object(content)
    return parse_event_batch_response(payload, events=prepared_events, max_tags=config.max_tags)


def fetch_event_texts(
    connection: Connection,
    *,
    event_id: int | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ["COALESCE(NULLIF(BTRIM(title), ''), NULLIF(BTRIM(description_text), ''), NULL) IS NOT NULL"]
    if event_id is not None:
        where.append("id = %s")
        params.append(event_id)
    sql = f"""
        SELECT
            id,
            title AS name,
            CONCAT_WS(
                '\n\n',
                NULLIF(BTRIM(title), ''),
                NULLIF(BTRIM(description_text), ''),
                NULLIF(BTRIM(lineup_residual_text), ''),
                NULLIF(BTRIM(lineup_raw), '')
            ) AS text
        FROM events
        WHERE {' AND '.join(where)}
        ORDER BY id ASC
    """
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


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
