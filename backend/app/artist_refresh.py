from __future__ import annotations

from typing import Any

from psycopg import Connection

from app.artist_tag_extraction import (
    TagExtractionConfig,
    create_extraction_client,
    extract_artist_tags_with_chunked_fallback,
    extract_artist_tags_with_llm,
    has_current_artist_tag_extraction,
    is_content_filter_error,
    replace_artist_tags,
    tag_extraction_text_hash,
)
from app.embeddings import (
    EmbeddingConfig,
    build_entity_text_profile,
    create_openai_embeddings,
    embedding_text_hash,
    has_current_embedding,
    upsert_entity_embedding,
)
from app.artist_tag_extraction import fetch_artist_biographies
from app.recommendations.jobs import invalidate_artist_promoter_jobs


SOURCE = "biography"


def refresh_artist_derived_data(connection: Connection, *, artist_id: int) -> dict[str, Any]:
    artists = fetch_artist_biographies(connection, artist_id=artist_id)
    if not artists:
        raise RuntimeError(f"Artist {artist_id} not found")

    artist = artists[0]
    invalidate_artist_promoter_jobs(
        connection,
        artist_id=artist_id,
        error_message="artist biography refreshed; promoter recommendation job invalidated",
    )
    tag_config = TagExtractionConfig.from_env()
    client = create_extraction_client(tag_config)
    biography = artist["biography"]
    tag_hash = tag_extraction_text_hash(biography)

    if not has_current_artist_tag_extraction(
        connection,
        artist_id=artist_id,
        source=SOURCE,
        extractor=tag_config.extractor_key,
        text_hash=tag_hash,
    ):
        try:
            tags = extract_artist_tags_with_llm(
                client,
                artist_name=artist["name"],
                biography=biography,
                config=tag_config,
            )
        except Exception as exc:
            if not is_content_filter_error(exc):
                raise

            fallback = extract_artist_tags_with_chunked_fallback(
                client,
                artist_name=artist["name"],
                biography=biography,
                config=tag_config,
            )
            if fallback.processed_chunks <= 0:
                raise RuntimeError(
                    f"All biography chunks were blocked by content_filter for artist {artist_id}"
                ) from exc
            tags = fallback.tags

        replace_artist_tags(
            connection,
            artist_id=artist_id,
            source=SOURCE,
            extractor=tag_config.extractor_key,
            text_hash=tag_hash,
            tags=tags,
        )
        connection.commit()

    embedding_config = EmbeddingConfig.from_env()
    text_profile = build_entity_text_profile(connection, "artist", artist_id)
    embedding_hash = embedding_text_hash(text_profile)
    if not has_current_embedding(
        connection,
        entity_type="artist",
        entity_id=artist_id,
        config=embedding_config,
        text_hash=embedding_hash,
    ):
        embedding = create_openai_embeddings([text_profile], embedding_config)[0]
        upsert_entity_embedding(
            connection,
            entity_type="artist",
            entity_id=artist_id,
            config=embedding_config,
            text_profile=text_profile,
            embedding=embedding,
        )
        connection.commit()

    return {
        "artistId": artist_id,
        "artistName": artist["name"],
        "tagsRefreshed": True,
        "embeddingsRefreshed": True,
    }
