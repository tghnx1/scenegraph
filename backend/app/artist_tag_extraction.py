from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Literal

from openai import AzureOpenAI, OpenAI
from psycopg import Connection

from app.text_profiles import normalize_biography_text, normalize_text, truncate_text


ExtractionProvider = Literal["openai", "azure"]
TagType = Literal["style", "label", "collective", "role", "residency", "alias"]

DEFAULT_EXTRACTION_MODEL = "gpt-4.1-mini"
DEFAULT_AZURE_CHAT_API_VERSION = "2025-01-01-preview"
MAX_BIOGRAPHY_CHARS = 6000
MAX_TAGS_PER_ARTIST = 32

ALLOWED_TAG_TYPES: set[str] = {
    "style",
    "label",
    "collective",
    "role",
    "residency",
    "alias",
}

LOW_CONFIDENCE_TYPES = {"alias", "residency"}


@dataclass(frozen=True)
class ArtistTag:
    tag_type: TagType
    tag_value: str
    confidence: float
    evidence: str | None = None


@dataclass(frozen=True)
class TagExtractionConfig:
    provider: ExtractionProvider = "openai"
    model: str = DEFAULT_EXTRACTION_MODEL
    max_biography_chars: int = MAX_BIOGRAPHY_CHARS
    max_tags: int = MAX_TAGS_PER_ARTIST

    @classmethod
    def from_env(cls) -> "TagExtractionConfig":
        provider = os.environ.get("EXTRACTION_PROVIDER", "openai").strip().lower() or "openai"
        if provider not in {"openai", "azure"}:
            raise ValueError("EXTRACTION_PROVIDER must be either 'openai' or 'azure'")

        if provider == "azure":
            model = (
                os.environ.get("AZURE_OPENAI_EXTRACTION_DEPLOYMENT", "").strip()
                or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "").strip()
            )
            if not model:
                raise ValueError(
                    "AZURE_OPENAI_EXTRACTION_DEPLOYMENT must be set when EXTRACTION_PROVIDER=azure"
                )
        else:
            model = (
                os.environ.get("OPENAI_EXTRACTION_MODEL", DEFAULT_EXTRACTION_MODEL).strip()
                or DEFAULT_EXTRACTION_MODEL
            )

        return cls(
            provider=provider,  # type: ignore[arg-type]
            model=model,
            max_biography_chars=int(
                os.environ.get("ARTIST_TAG_EXTRACTION_MAX_BIO_CHARS", MAX_BIOGRAPHY_CHARS)
            ),
            max_tags=int(os.environ.get("ARTIST_TAG_EXTRACTION_MAX_TAGS", MAX_TAGS_PER_ARTIST)),
        )

    @property
    def extractor_key(self) -> str:
        return f"llm_artist_tags_v1:{self.provider}:{self.model}"


def tag_extraction_text_hash(text: str) -> str:
    return hashlib.sha256(normalize_biography_text(text).encode("utf-8")).hexdigest()


def create_chat_client(config: TagExtractionConfig) -> OpenAI | AzureOpenAI:
    if config.provider == "azure":
        if not os.environ.get("AZURE_OPENAI_API_KEY"):
            raise RuntimeError("AZURE_OPENAI_API_KEY must be set for Azure tag extraction")
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
        if not endpoint:
            raise RuntimeError("AZURE_OPENAI_ENDPOINT must be set for Azure tag extraction")

        return AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            azure_endpoint=endpoint,
            api_version=os.environ.get("AZURE_OPENAI_CHAT_API_VERSION", DEFAULT_AZURE_CHAT_API_VERSION),
        )

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY must be set for OpenAI tag extraction")
    return OpenAI()


def system_prompt() -> str:
    return (
        "You extract structured music-scene facts from artist biographies. "
        "Return only JSON. Extract only facts explicitly supported by the biography; do not guess. "
        "Do not extract cities, countries, or generic venues played unless the text says the artist is a resident. "
        "Do not repeat the artist's own name as an alias."
    )


def user_prompt(artist_name: str, biography: str, max_tags: int) -> str:
    return f"""
Artist name: {artist_name}

Biography:
{biography}

Return JSON in this exact shape:
{{
  "tags": [
    {{
      "type": "style|label|collective|role|residency|alias",
      "value": "short normalized tag",
      "confidence": 0.0,
      "evidence": "short phrase from the biography"
    }}
  ]
}}

Extraction rules:
- style: genres or sound descriptors such as dark disco, EBM, electro, industrial, minimal, house.
- label: record labels, imprints, release platforms, or label affiliations.
- collective: crews, groups, communities, or artistic collectives.
- role: artist roles such as DJ, producer, live act, vocalist, promoter, curator, resident.
- residency: a named party, venue, radio show, or platform where the biography says the artist is/was resident.
- alias: alternate artist names only when the biography clearly presents them as aliases.
- Keep at most {max_tags} tags total.
- Prefer fewer high-confidence tags over many weak tags.
""".strip()


def extract_json_object(value: str) -> dict[str, Any]:
    text = value.strip()
    if not text:
        return {}

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise ValueError("Tag extraction response must be a JSON object")
    return parsed


def normalize_tag_value(tag_type: str, value: Any) -> str:
    text = normalize_text(value).strip(" \t\n\r,.;:|/\\")
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    if tag_type in {"style", "role"}:
        text = text.lower()
    return text[:120].strip()


def normalize_confidence(value: Any, *, tag_type: str) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.7 if tag_type not in LOW_CONFIDENCE_TYPES else 0.55

    return max(0.0, min(confidence, 1.0))


def parse_tags_response(payload: dict[str, Any], *, artist_name: str, max_tags: int) -> list[ArtistTag]:
    raw_tags = payload.get("tags", [])
    if not isinstance(raw_tags, list):
        return []

    artist_name_key = normalize_text(artist_name).casefold()
    seen: set[tuple[str, str]] = set()
    tags: list[ArtistTag] = []

    for item in raw_tags:
        if not isinstance(item, dict):
            continue

        tag_type = normalize_text(item.get("type")).lower()
        if tag_type not in ALLOWED_TAG_TYPES:
            continue

        tag_value = normalize_tag_value(tag_type, item.get("value"))
        if len(tag_value) < 2 or tag_value.casefold() == artist_name_key:
            continue

        key = (tag_type, tag_value.casefold())
        if key in seen:
            continue

        evidence = truncate_text(item.get("evidence", ""), 300) or None
        tags.append(
            ArtistTag(
                tag_type=tag_type,  # type: ignore[arg-type]
                tag_value=tag_value,
                confidence=normalize_confidence(item.get("confidence"), tag_type=tag_type),
                evidence=evidence,
            )
        )
        seen.add(key)

        if len(tags) >= max_tags:
            break

    return tags


def extract_artist_tags_with_llm(
    client: OpenAI | AzureOpenAI,
    *,
    artist_name: str,
    biography: str,
    config: TagExtractionConfig,
) -> list[ArtistTag]:
    normalized_biography = truncate_text(
        normalize_biography_text(biography),
        config.max_biography_chars,
    )
    if not normalized_biography:
        return []

    response = client.chat.completions.create(
        model=config.model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": user_prompt(artist_name, normalized_biography, config.max_tags)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    payload = extract_json_object(content)
    return parse_tags_response(payload, artist_name=artist_name, max_tags=config.max_tags)


def fetch_artist_biographies(
    connection: Connection,
    *,
    artist_id: int | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = [
        "COALESCE(NULLIF(BTRIM(biography_normalized), ''), NULLIF(BTRIM(biography), '')) IS NOT NULL"
    ]

    if artist_id is not None:
        where.append("id = %s")
        params.append(artist_id)

    sql = f"""
        SELECT
            id,
            name,
            COALESCE(biography_normalized, biography, '') AS biography
        FROM artists
        WHERE {' AND '.join(where)}
        ORDER BY id ASC
    """
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def has_current_artist_tag_extraction(
    connection: Connection,
    *,
    artist_id: int,
    source: str,
    extractor: str,
    text_hash: str,
) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM artist_tag_extraction_runs
            WHERE artist_id = %s
              AND source = %s
              AND extractor = %s
              AND text_hash = %s
            LIMIT 1
            """,
            (artist_id, source, extractor, text_hash),
        )
        return cursor.fetchone() is not None


def replace_artist_tags(
    connection: Connection,
    *,
    artist_id: int,
    source: str,
    extractor: str,
    text_hash: str,
    tags: list[ArtistTag],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM artist_extracted_tags
            WHERE artist_id = %s
              AND source = %s
              AND extractor = %s
            """,
            (artist_id, source, extractor),
        )

        for tag in tags:
            cursor.execute(
                """
                INSERT INTO artist_extracted_tags (
                    artist_id, tag_type, tag_value, source, confidence, extractor, evidence
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    artist_id,
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
            INSERT INTO artist_tag_extraction_runs (
                artist_id, source, extractor, text_hash, tag_count
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (artist_id, source, extractor) DO UPDATE SET
                text_hash = EXCLUDED.text_hash,
                tag_count = EXCLUDED.tag_count,
                updated_at = CURRENT_TIMESTAMP
            """,
            (artist_id, source, extractor, text_hash, len(tags)),
        )
