import argparse
import os
import sys
from pathlib import Path
from typing import Literal

import psycopg
from psycopg.rows import dict_row

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.embeddings import (
    EmbeddingConfig,
    EntityType,
    build_entity_text_profile,
    create_openai_embeddings,
    embedding_text_hash,
    fetch_entity_ids,
    has_current_embedding,
    upsert_entity_embedding,
)


DATABASE_URL = os.environ["DATABASE_URL"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate OpenAI embeddings for recommendation entities.")
    parser.add_argument(
        "--entity",
        choices=("event", "artist", "all"),
        default="all",
        help="Entity type to embed. Defaults to all.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum entities per type.")
    parser.add_argument("--batch-size", type=int, default=64, help="OpenAI embeddings batch size.")
    parser.add_argument("--force", action="store_true", help="Regenerate embeddings even if text is unchanged.")
    return parser.parse_args()


def entity_types(selection: Literal["event", "artist", "all"]) -> list[EntityType]:
    if selection == "all":
        return ["event", "artist"]
    return [selection]


def flush_batch(
    connection: psycopg.Connection,
    *,
    config: EmbeddingConfig,
    batch: list[tuple[EntityType, int, str]],
) -> int:
    if not batch:
        return 0

    vectors = create_openai_embeddings([item[2] for item in batch], config)
    for (entity_type, entity_id, text_profile), vector in zip(batch, vectors, strict=True):
        upsert_entity_embedding(
            connection,
            entity_type=entity_type,
            entity_id=entity_id,
            config=config,
            text_profile=text_profile,
            embedding=vector,
        )

    connection.commit()
    return len(batch)


def main() -> None:
    args = parse_args()
    config = EmbeddingConfig.from_env()

    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")
    if config.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY must be set to generate embeddings")
    if config.provider == "azure":
        if not os.environ.get("AZURE_OPENAI_API_KEY"):
            raise SystemExit("AZURE_OPENAI_API_KEY must be set to generate Azure embeddings")
        if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
            raise SystemExit("AZURE_OPENAI_ENDPOINT must be set to generate Azure embeddings")

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        total_embedded = 0
        total_skipped = 0

        for entity_type in entity_types(args.entity):
            ids = fetch_entity_ids(connection, entity_type, args.limit)
            batch: list[tuple[EntityType, int, str]] = []

            for entity_id in ids:
                text_profile = build_entity_text_profile(connection, entity_type, entity_id)
                text_hash = embedding_text_hash(text_profile)

                if not args.force and has_current_embedding(
                    connection,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    config=config,
                    text_hash=text_hash,
                ):
                    total_skipped += 1
                    continue

                batch.append((entity_type, entity_id, text_profile))
                if len(batch) >= args.batch_size:
                    total_embedded += flush_batch(connection, config=config, batch=batch)
                    print(f"Embedded {total_embedded} entities; skipped {total_skipped}")
                    batch.clear()

            total_embedded += flush_batch(connection, config=config, batch=batch)
            print(f"Finished {entity_type}: {len(ids)} checked")

    print(
        f"Embedding sync complete with model={config.provider_model_key}; "
        f"embedded={total_embedded}; skipped={total_skipped}"
    )


if __name__ == "__main__":
    main()
