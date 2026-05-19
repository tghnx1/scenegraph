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

from app.text_profiles import normalize_biography_text, normalize_text, truncate_text


ExtractionProvider = Literal["openai", "azure"]
ExtractionApi = Literal["chat_completions", "responses"]
TagType = Literal["style", "label", "collective", "role", "residency", "alias"]

DEFAULT_EXTRACTION_MODEL = "gpt-4.1-mini"
DEFAULT_AZURE_CHAT_API_VERSION = "2025-01-01-preview"
DEFAULT_AZURE_RESPONSES_API_VERSION = "2025-04-01-preview"
MAX_BIOGRAPHY_CHARS = 6000
MAX_TAGS_PER_ARTIST = 32
CHUNK_FALLBACK_CHARS = 600

ALLOWED_TAG_TYPES: set[str] = {
    "style",
    "label",
    "collective",
    "role",
    "residency",
    "alias",
}

LOW_CONFIDENCE_TYPES = {"alias", "residency"}
SCENE_ENTITY_TAG_TYPES = {"label", "collective", "residency"}

GENERIC_ENTITY_SUFFIXES_BY_TYPE: dict[str, tuple[str, ...]] = {
    "label": (
        "record label",
        "recording label",
        "label",
        "records",
        "recordings",
        "rec",
        "rec.",
        "imprint",
    ),
    "collective": (
        "music association e.v.",
        "music association",
        "music collective",
        "artist collective",
        "art collective",
        "artistic collective",
        "association",
        "collective",
        "community",
        "crew",
        "group",
    ),
    "residency": (
        "resident dj",
        "resident",
        "residents",
        "residency",
    ),
}

GENERIC_TAG_VALUES_BY_TYPE: dict[str, set[str]] = {
    "label": {
        "apple music",
        "bandcamp",
        "beatport",
        "discogs",
        "facebook",
        "instagram",
        "mixcloud",
        "resident advisor",
        "ra",
        "soundcloud",
        "spotify",
        "tidal",
        "youtube",
    },
    "residency": {
        "berlin",
        "germany",
        "london",
        "new york",
        "paris",
        "tokyo",
    },
}

ENTITY_VALUE_PREFIX_RE = re.compile(
    r"(?i)^(?:"
    r"resident(?:\s+dj)?\s+(?:at|of|for)\s+|"
    r"residency\s+(?:at|of|for)\s+|"
    r"member\s+of\s+|"
    r"co-?founder\s+of\s+|"
    r"founder\s+of\s+|"
    r"part\s+of\s+|"
    r"signed\s+to\s+|"
    r"released\s+on\s+|"
    r"affiliated\s+with\s+"
    r")"
)


@dataclass(frozen=True)
class ArtistTag:
    tag_type: TagType
    tag_value: str
    confidence: float
    evidence: str | None = None


@dataclass(frozen=True)
class ChunkedTagExtractionResult:
    tags: list[ArtistTag]
    total_chunks: int
    processed_chunks: int
    skipped_chunks: int


@dataclass(frozen=True)
class TagExtractionConfig:
    provider: ExtractionProvider = "openai"
    model: str = DEFAULT_EXTRACTION_MODEL
    api: ExtractionApi = "chat_completions"
    azure_responses_url: str | None = None
    max_biography_chars: int = MAX_BIOGRAPHY_CHARS
    max_tags: int = MAX_TAGS_PER_ARTIST
    chunk_chars: int = CHUNK_FALLBACK_CHARS

    @classmethod
    def from_env(cls) -> "TagExtractionConfig":
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
            model = (
                os.environ.get("OPENAI_EXTRACTION_MODEL", DEFAULT_EXTRACTION_MODEL).strip()
                or DEFAULT_EXTRACTION_MODEL
            )

        return cls(
            provider=provider,  # type: ignore[arg-type]
            model=model,
            api=api,  # type: ignore[arg-type]
            azure_responses_url=azure_responses_url or None,
            max_biography_chars=int(
                os.environ.get("ARTIST_TAG_EXTRACTION_MAX_BIO_CHARS", MAX_BIOGRAPHY_CHARS)
            ),
            max_tags=int(os.environ.get("ARTIST_TAG_EXTRACTION_MAX_TAGS", MAX_TAGS_PER_ARTIST)),
            chunk_chars=int(
                os.environ.get("ARTIST_TAG_EXTRACTION_CHUNK_CHARS", CHUNK_FALLBACK_CHARS)
            ),
        )

    @property
    def extractor_key(self) -> str:
        return f"llm_artist_tags_v1:{self.provider}:{self.api}:{self.model}"


def tag_extraction_text_hash(text: str) -> str:
    return hashlib.sha256(normalize_biography_text(text).encode("utf-8")).hexdigest()


def create_extraction_client(config: TagExtractionConfig) -> OpenAI | AzureOpenAI | None:
    if config.provider == "azure" and config.api == "responses":
        if not os.environ.get("AZURE_OPENAI_API_KEY"):
            raise RuntimeError("AZURE_OPENAI_API_KEY must be set for Azure tag extraction")
        if not config.azure_responses_url:
            raise RuntimeError("AZURE_OPENAI_RESPONSES_URL must be set for Azure Responses tag extraction")
        return None

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


def create_chat_client(config: TagExtractionConfig) -> OpenAI | AzureOpenAI | None:
    return create_extraction_client(config)


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
- Do not extract websites or generic platforms such as Bandcamp, SoundCloud, Spotify, Instagram, YouTube, RA, or Discogs.
- Do not extract cities, countries, regions, or scenes as residency tags.
- Keep at most {max_tags} tags total.
- Prefer fewer high-confidence tags over many weak tags.
""".strip()


def batch_user_prompt(artists: list[dict[str, Any]], max_tags: int) -> str:
    artist_blocks = []
    for artist in artists:
        artist_blocks.append(
            f"""
Artist ID: {artist["id"]}
Artist name: {artist["name"]}

Biography:
{artist["biography"]}
""".strip()
        )
    artist_text = "\n\n---\n\n".join(artist_blocks)

    return f"""
Artists:

{artist_text}

Return JSON in this exact shape:
{{
  "artists": [
    {{
      "artistId": 123,
      "tags": [
        {{
          "type": "style|label|collective|role|residency|alias",
          "value": "short normalized tag",
          "confidence": 0.0,
          "evidence": "short phrase from that artist biography"
        }}
      ]
    }}
  ]
}}

Extraction rules:
- Extract tags independently for each artist ID.
- style: genres or sound descriptors such as dark disco, EBM, electro, industrial, minimal, house.
- label: record labels, imprints, release platforms, or label affiliations.
- collective: crews, groups, communities, or artistic collectives.
- role: artist roles such as DJ, producer, live act, vocalist, promoter, curator, resident.
- residency: a named party, venue, radio show, or platform where the biography says the artist is/was resident.
- alias: alternate artist names only when the biography clearly presents them as aliases.
- Do not extract websites or generic platforms such as Bandcamp, SoundCloud, Spotify, Instagram, YouTube, RA, or Discogs.
- Do not extract cities, countries, regions, or scenes as residency tags.
- Keep at most {max_tags} tags per artist.
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


def is_content_filter_error(error: BaseException) -> bool:
    message = str(error).casefold()
    return (
        "content_filter" in message
        or "responsibleaipolicyviolation" in message
        or "content management policy" in message
    )


def normalize_tag_value(tag_type: str, value: Any) -> str:
    text = normalize_text(value).strip(" \t\n\r,.;:|/\\")
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    if tag_type in {"style", "role"}:
        text = text.lower()
    elif tag_type in SCENE_ENTITY_TAG_TYPES:
        text = normalize_scene_entity_tag(tag_type, text)
    return text[:120].strip()


def normalize_scene_entity_tag(tag_type: str, value: str) -> str:
    text = value.strip(" \t\n\r,.;:|/\\")
    text = re.sub(
        r"(?i)\s+\((?:record label|label|imprint|collective|crew|resident|residency)\)$",
        "",
        text,
    ).strip(" \t\n\r,.;:|/\\")

    while True:
        without_prefix = ENTITY_VALUE_PREFIX_RE.sub("", text).strip(" \t\n\r,.;:|/\\")
        if without_prefix == text:
            break
        text = without_prefix

    suffix_removed = False
    suffixes = GENERIC_ENTITY_SUFFIXES_BY_TYPE.get(tag_type, ())
    while True:
        changed = False
        for suffix in sorted(suffixes, key=len, reverse=True):
            pattern = re.compile(rf"(?i)(?:[\s-]+){re.escape(suffix)}\.?$")
            match = pattern.search(text)
            if not match:
                continue
            candidate = text[: match.start()].strip(" \t\n\r,.;:|/\\-")
            if len(candidate) < 2:
                continue
            text = candidate
            suffix_removed = True
            changed = True
            break
        if not changed:
            break

    if suffix_removed:
        text = re.sub(r"(?i)^the\s+", "", text).strip(" \t\n\r,.;:|/\\")

    return text


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
        if is_generic_tag_value(tag_type, tag_value):
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


def merge_artist_tags(tag_groups: list[list[ArtistTag]], *, max_tags: int) -> list[ArtistTag]:
    merged: dict[tuple[str, str], ArtistTag] = {}
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


def is_generic_tag_value(tag_type: str, tag_value: str) -> bool:
    values = GENERIC_TAG_VALUES_BY_TYPE.get(tag_type)
    if not values:
        return False
    return tag_value.casefold() in values


def parse_artist_batch_response(
    payload: dict[str, Any],
    *,
    artists: list[dict[str, Any]],
    max_tags: int,
) -> dict[int, list[ArtistTag]]:
    raw_artists = payload.get("artists", [])
    if not isinstance(raw_artists, list):
        return {}

    artist_names = {int(artist["id"]): artist["name"] for artist in artists}
    results: dict[int, list[ArtistTag]] = {}

    for item in raw_artists:
        if not isinstance(item, dict):
            continue

        raw_artist_id = item.get("artistId", item.get("artist_id", item.get("id")))
        try:
            artist_id = int(raw_artist_id)
        except (TypeError, ValueError):
            continue

        artist_name = artist_names.get(artist_id)
        if not artist_name:
            continue

        results[artist_id] = parse_tags_response(
            {"tags": item.get("tags", [])},
            artist_name=artist_name,
            max_tags=max_tags,
        )

    return results


def extract_responses_output_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text

    chunks: list[str] = []
    for output_item in payload.get("output", []):
        if not isinstance(output_item, dict):
            continue
        for content_item in output_item.get("content", []):
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str):
                chunks.append(text)

    return "\n".join(chunks)


def create_azure_responses_completion(*, prompt: str, config: TagExtractionConfig) -> str:
    if not config.azure_responses_url:
        raise RuntimeError("AZURE_OPENAI_RESPONSES_URL must be set for Azure Responses tag extraction")

    response = httpx.post(
        config.azure_responses_url,
        headers={
            "api-key": os.environ["AZURE_OPENAI_API_KEY"],
            "Content-Type": "application/json",
        },
        json={
            "model": config.model,
            "instructions": system_prompt(),
            "input": prompt,
            "store": False,
            "temperature": 0,
            "text": {"format": {"type": "json_object"}},
        },
        timeout=60,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Azure Responses API failed with HTTP {response.status_code}: {response.text[:500]}"
        ) from exc

    content = extract_responses_output_text(response.json())
    if not content:
        raise RuntimeError("Azure Responses API returned no output text")
    return content


def create_chat_completion(
    client: OpenAI | AzureOpenAI | None,
    *,
    prompt: str,
    config: TagExtractionConfig,
) -> str:
    if client is None:
        raise RuntimeError("Chat completions extraction requires a client")

    response = client.chat.completions.create(
        model=config.model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or "{}"


SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def split_biography_chunks(value: str, *, max_chars: int) -> list[str]:
    if max_chars < 80:
        raise ValueError("Chunk size must be at least 80 characters")

    text = normalize_biography_text(value)
    if not text:
        return []

    chunks: list[str] = []
    current = ""

    def append_piece(piece: str) -> None:
        nonlocal current
        piece = piece.strip()
        if not piece:
            return

        if len(piece) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            remaining = piece
            while len(remaining) > max_chars:
                chunk = remaining[:max_chars].rsplit(" ", 1)[0].strip()
                if not chunk:
                    chunk = remaining[:max_chars].strip()
                chunks.append(chunk)
                remaining = remaining[len(chunk) :].strip()
            current = remaining
            return

        candidate = f"{current} {piece}".strip() if current else piece
        if len(candidate) <= max_chars:
            current = candidate
            return

        if current:
            chunks.append(current)
        current = piece

    for sentence in SENTENCE_BOUNDARY_RE.split(text):
        append_piece(sentence)

    if current:
        chunks.append(current)

    return chunks


def extract_artist_tags_with_llm(
    client: OpenAI | AzureOpenAI | None,
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

    if config.provider == "azure" and config.api == "responses":
        content = create_azure_responses_completion(
            prompt=user_prompt(artist_name, normalized_biography, config.max_tags),
            config=config,
        )
    else:
        content = create_chat_completion(
            client,
            prompt=user_prompt(artist_name, normalized_biography, config.max_tags),
            config=config,
        )

    payload = extract_json_object(content)
    return parse_tags_response(payload, artist_name=artist_name, max_tags=config.max_tags)


def extract_artist_tags_with_chunked_fallback(
    client: OpenAI | AzureOpenAI | None,
    *,
    artist_name: str,
    biography: str,
    config: TagExtractionConfig,
) -> ChunkedTagExtractionResult:
    chunks = split_biography_chunks(biography, max_chars=config.chunk_chars)
    tag_groups: list[list[ArtistTag]] = []
    skipped_chunks = 0

    for chunk in chunks:
        try:
            tag_groups.append(
                extract_artist_tags_with_llm(
                    client,
                    artist_name=artist_name,
                    biography=chunk,
                    config=config,
                )
            )
        except Exception as exc:
            if not is_content_filter_error(exc):
                raise
            skipped_chunks += 1

    processed_chunks = len(chunks) - skipped_chunks
    return ChunkedTagExtractionResult(
        tags=merge_artist_tags(tag_groups, max_tags=config.max_tags),
        total_chunks=len(chunks),
        processed_chunks=processed_chunks,
        skipped_chunks=skipped_chunks,
    )


def extract_artist_tag_batch_with_llm(
    client: OpenAI | AzureOpenAI | None,
    *,
    artists: list[dict[str, Any]],
    config: TagExtractionConfig,
) -> dict[int, list[ArtistTag]]:
    prepared_artists = []
    for artist in artists:
        normalized_biography = truncate_text(
            normalize_biography_text(artist["biography"]),
            config.max_biography_chars,
        )
        if not normalized_biography:
            continue
        prepared_artists.append(
            {
                "id": artist["id"],
                "name": artist["name"],
                "biography": normalized_biography,
            }
        )

    if not prepared_artists:
        return {}

    prompt = batch_user_prompt(prepared_artists, config.max_tags)
    if config.provider == "azure" and config.api == "responses":
        content = create_azure_responses_completion(prompt=prompt, config=config)
    else:
        content = create_chat_completion(client, prompt=prompt, config=config)

    payload = extract_json_object(content)
    return parse_artist_batch_response(
        payload,
        artists=prepared_artists,
        max_tags=config.max_tags,
    )


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
