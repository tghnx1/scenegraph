from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass
from typing import Any, Literal

from openai import AzureOpenAI, OpenAI
from psycopg import Connection

from app.text_profiles import (
    build_artist_text_profile,
    build_event_text_profile,
    normalize_text,
)


EntityType = Literal["artist", "event"]
EmbeddingProvider = Literal["openai", "azure"]
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_AZURE_OPENAI_API_VERSION = "2024-02-01"


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: EmbeddingProvider = "openai"
    model: str = DEFAULT_EMBEDDING_MODEL
    dimensions: int | None = None

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        dimensions = os.environ.get("OPENAI_EMBEDDING_DIMENSIONS", "").strip()
        provider = os.environ.get("EMBEDDING_PROVIDER", "openai").strip().lower() or "openai"
        if provider not in {"openai", "azure"}:
            raise ValueError("EMBEDDING_PROVIDER must be either 'openai' or 'azure'")

        if provider == "azure":
            model = (
                os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "").strip()
                or os.environ.get("OPENAI_EMBEDDING_MODEL", "").strip()
            )
            if not model:
                raise ValueError(
                    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT must be set when EMBEDDING_PROVIDER=azure"
                )
        else:
            model = (
                os.environ.get("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip()
                or DEFAULT_EMBEDDING_MODEL
            )

        return cls(
            provider=provider,  # type: ignore[arg-type]
            model=model,
            dimensions=int(dimensions) if dimensions else None,
        )

    @property
    def provider_model_key(self) -> str:
        return f"{self.provider}:{self.model}"


def embedding_text_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions must match")

    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def embedding_vector_literal(values: list[float]) -> str:
    """Convert a Python float list into pgvector literal format."""
    if not values:
        raise ValueError("Embedding vector cannot be empty")
    return "[" + ",".join(format(value, ".15g") for value in values) + "]"


def embedding_vector_supported(connection: Connection) -> bool:
    """Check whether pgvector extension and embedding_vec column are available."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                EXISTS (
                    SELECT 1
                    FROM pg_extension
                    WHERE extname = 'vector'
                ) AS has_vector_extension,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'entity_embeddings'
                      AND column_name = 'embedding_vec'
                ) AS has_embedding_vec_column
            """
        )
        row = cursor.fetchone()
    return bool(row and row["has_vector_extension"] and row["has_embedding_vec_column"])


def create_openai_embeddings(texts: list[str], config: EmbeddingConfig) -> list[list[float]]:
    if config.provider == "azure":
        if not os.environ.get("AZURE_OPENAI_API_KEY"):
            raise RuntimeError("AZURE_OPENAI_API_KEY must be set to generate Azure embeddings")
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
        if not endpoint:
            raise RuntimeError("AZURE_OPENAI_ENDPOINT must be set to generate Azure embeddings")

        client: OpenAI | AzureOpenAI = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            azure_endpoint=endpoint,
            api_version=os.environ.get(
                "AZURE_OPENAI_API_VERSION",
                DEFAULT_AZURE_OPENAI_API_VERSION,
            ),
        )
    else:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY must be set to generate embeddings")
        client = OpenAI()

    request: dict[str, Any] = {
        "model": config.model,
        "input": texts,
    }
    if config.dimensions is not None:
        request["dimensions"] = config.dimensions

    response = client.embeddings.create(**request)
    vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]

    if len(vectors) != len(texts):
        raise RuntimeError("OpenAI embeddings response did not match input batch size")

    return vectors


def build_entity_text_profile(
    connection: Connection,
    entity_type: EntityType,
    entity_id: int,
) -> str:
    if entity_type == "event":
        return build_event_text_profile(connection, entity_id)
    if entity_type == "artist":
        return build_artist_text_profile(connection, entity_id)
    raise ValueError(f"Unsupported entity type: {entity_type}")


def fetch_entity_ids(
    connection: Connection,
    entity_type: EntityType,
    limit: int | None = None,
    ids: list[int] | None = None,
) -> list[int]:
    table = "events" if entity_type == "event" else "artists"
    sql = f"SELECT id FROM {table}"
    params: list[Any] = []
    where: list[str] = []

    if ids is not None:
        if not ids:
            return []
        where.append("id = ANY(%s)")
        params.append(ids)

    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id ASC"
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return [row["id"] for row in cursor.fetchall()]


def has_current_embedding(
    connection: Connection,
    *,
    entity_type: EntityType,
    entity_id: int,
    config: EmbeddingConfig,
    text_hash: str,
) -> bool:
    dimensions_filter = ""
    params: list[Any] = [entity_type, entity_id, config.provider_model_key, text_hash]

    if config.dimensions is not None:
        dimensions_filter = "AND dimensions = %s"
        params.append(config.dimensions)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT 1
            FROM entity_embeddings
            WHERE entity_type = %s
              AND entity_id = %s
              AND model = %s
              AND text_hash = %s
              {dimensions_filter}
            LIMIT 1
            """,
            params,
        )
        return cursor.fetchone() is not None


def upsert_entity_embedding(
    connection: Connection,
    *,
    entity_type: EntityType,
    entity_id: int,
    config: EmbeddingConfig,
    text_profile: str,
    embedding: list[float],
) -> None:
    dimensions = len(embedding)
    if config.dimensions is not None and dimensions != config.dimensions:
        raise ValueError(
            f"Expected {config.dimensions} dimensions from {config.provider_model_key}, got {dimensions}"
        )

    vector_supported = embedding_vector_supported(connection)

    with connection.cursor() as cursor:
        if vector_supported and dimensions == 1536:
            cursor.execute(
                """
                INSERT INTO entity_embeddings (
                    entity_type,
                    entity_id,
                    model,
                    dimensions,
                    text_hash,
                    text_profile,
                    embedding,
                    embedding_vec
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (entity_type, entity_id, model, dimensions) DO UPDATE SET
                    text_hash = EXCLUDED.text_hash,
                    text_profile = EXCLUDED.text_profile,
                    embedding = EXCLUDED.embedding,
                    embedding_vec = EXCLUDED.embedding_vec,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    entity_type,
                    entity_id,
                    config.provider_model_key,
                    dimensions,
                    embedding_text_hash(text_profile),
                    text_profile,
                    embedding,
                    embedding_vector_literal(embedding),
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO entity_embeddings (
                    entity_type, entity_id, model, dimensions, text_hash, text_profile, embedding
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (entity_type, entity_id, model, dimensions) DO UPDATE SET
                    text_hash = EXCLUDED.text_hash,
                    text_profile = EXCLUDED.text_profile,
                    embedding = EXCLUDED.embedding,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    entity_type,
                    entity_id,
                    config.provider_model_key,
                    dimensions,
                    embedding_text_hash(text_profile),
                    text_profile,
                    embedding,
                ),
            )


def load_source_embedding(
    connection: Connection,
    *,
    entity_type: EntityType,
    entity_id: int,
    config: EmbeddingConfig,
) -> dict[str, Any] | None:
    vector_supported = embedding_vector_supported(connection)
    dimensions_filter = ""
    params: list[Any] = [entity_type, entity_id, config.provider_model_key]

    if config.dimensions is not None:
        dimensions_filter = "AND dimensions = %s"
        params.append(config.dimensions)

    with connection.cursor() as cursor:
        if vector_supported:
            cursor.execute(
                f"""
                SELECT
                    entity_id,
                    model,
                    dimensions,
                    embedding,
                    embedding_vec::text AS embedding_vec
                FROM entity_embeddings
                WHERE entity_type = %s
                  AND entity_id = %s
                  AND model = %s
                  AND embedding_vec IS NOT NULL
                  {dimensions_filter}
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                params,
            )
        else:
            cursor.execute(
                f"""
                SELECT
                    entity_id,
                    model,
                    dimensions,
                    embedding,
                    NULL::text AS embedding_vec
                FROM entity_embeddings
                WHERE entity_type = %s
                  AND entity_id = %s
                  AND model = %s
                  {dimensions_filter}
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                params,
            )
        return cursor.fetchone()


def rank_similar_embeddings(
    connection: Connection,
    *,
    entity_type: EntityType,
    entity_id: int,
    config: EmbeddingConfig,
    limit: int,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    vector_supported = embedding_vector_supported(connection)
    source = load_source_embedding(
        connection,
        entity_type=entity_type,
        entity_id=entity_id,
        config=config,
    )
    if source is None:
        return None, []

    source_embedding_vec = source.get("embedding_vec")
    if vector_supported and isinstance(source_embedding_vec, str) and source_embedding_vec.strip():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    entity_id,
                    GREATEST(
                        1 - (embedding_vec <=> %s::vector),
                        0.0
                    )::double precision AS score
                FROM entity_embeddings
                WHERE entity_type = %s
                  AND entity_id <> %s
                  AND model = %s
                  AND dimensions = %s
                  AND embedding_vec IS NOT NULL
                ORDER BY embedding_vec <=> %s::vector ASC, entity_id ASC
                LIMIT %s
                """,
                (
                    source_embedding_vec,
                    entity_type,
                    entity_id,
                    source["model"],
                    source["dimensions"],
                    source_embedding_vec,
                    max(limit, 1),
                ),
            )
            candidates = cursor.fetchall()

        return source, [
            {
                "entity_id": int(candidate["entity_id"]),
                "score": float(candidate["score"]),
            }
            for candidate in candidates
        ]

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT entity_id, embedding
            FROM entity_embeddings
            WHERE entity_type = %s
              AND entity_id <> %s
              AND model = %s
              AND dimensions = %s
            """,
            (entity_type, entity_id, source["model"], source["dimensions"]),
        )
        candidates = cursor.fetchall()

    ranked = sorted(
        (
            {
                "entity_id": int(candidate["entity_id"]),
                "score": cosine_similarity(source["embedding"], candidate["embedding"]),
            }
            for candidate in candidates
        ),
        key=lambda candidate: (-candidate["score"], candidate["entity_id"]),
    )
    return source, ranked[:limit]
