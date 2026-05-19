import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.artist_tag_extraction import (
    TagExtractionConfig,
    create_extraction_client,
    extract_artist_tag_batch_with_llm,
    extract_artist_tags_with_llm,
    fetch_artist_biographies,
    has_current_artist_tag_extraction,
    replace_artist_tags,
    tag_extraction_text_hash,
)


DATABASE_URL = os.environ["DATABASE_URL"]
SOURCE = "biography"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract structured artist tags from biographies with an LLM.")
    parser.add_argument("--artist-id", type=int, default=None, help="Extract tags for one artist id.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum artists to process.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Number of artists to send to the LLM per request. Use 1 for one-by-one extraction.",
    )
    parser.add_argument("--force", action="store_true", help="Re-extract even if the biography hash is unchanged.")
    parser.add_argument("--dry-run", action="store_true", help="Print extracted tags without writing to the database.")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue after one artist fails instead of stopping the run.",
    )
    return parser.parse_args()


def ensure_provider_env(config: TagExtractionConfig) -> None:
    if config.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY must be set for OpenAI tag extraction")

    if config.provider == "azure":
        if not os.environ.get("AZURE_OPENAI_API_KEY"):
            raise SystemExit("AZURE_OPENAI_API_KEY must be set for Azure tag extraction")
        if config.api == "responses":
            if not config.azure_responses_url:
                raise SystemExit("AZURE_OPENAI_RESPONSES_URL must be set for Azure Responses tag extraction")
        elif not os.environ.get("AZURE_OPENAI_ENDPOINT"):
            raise SystemExit("AZURE_OPENAI_ENDPOINT must be set for Azure tag extraction")


def main() -> None:
    args = parse_args()
    config = TagExtractionConfig.from_env()
    ensure_provider_env(config)

    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")
    if args.artist_id is not None and args.batch_size != 1:
        args.batch_size = 1

    client = create_extraction_client(config)
    processed = 0
    skipped = 0
    failed = 0

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        artists = fetch_artist_biographies(
            connection,
            artist_id=args.artist_id,
            limit=args.limit,
        )

        def write_artist_tags(artist: dict, tags: list) -> None:
            nonlocal processed
            if args.dry_run:
                print(
                    json.dumps(
                        {
                            "artistId": artist["id"],
                            "artistName": artist["name"],
                            "extractor": config.extractor_key,
                            "tags": [
                                {
                                    "type": tag.tag_type,
                                    "value": tag.tag_value,
                                    "confidence": tag.confidence,
                                    "evidence": tag.evidence,
                                }
                                for tag in tags
                            ],
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                replace_artist_tags(
                    connection,
                    artist_id=artist["id"],
                    source=SOURCE,
                    extractor=config.extractor_key,
                    text_hash=artist["_text_hash"],
                    tags=tags,
                )
                connection.commit()

            processed += 1

        def process_one(artist: dict) -> bool:
            nonlocal failed
            try:
                tags = extract_artist_tags_with_llm(
                    client,
                    artist_name=artist["name"],
                    biography=artist["biography"],
                    config=config,
                )
            except Exception as exc:
                failed += 1
                print(f"Failed artist {artist['id']} {artist['name']}: {exc}", file=sys.stderr)
                if not args.continue_on_error:
                    raise
                return False

            write_artist_tags(artist, tags)
            return True

        def process_batch(batch: list[dict]) -> None:
            nonlocal failed
            if not batch:
                return

            if args.batch_size == 1 or len(batch) == 1:
                for batch_artist in batch:
                    process_one(batch_artist)
                    print(f"Processed {processed} artists; skipped {skipped}; failed {failed}")
                return

            try:
                batch_results = extract_artist_tag_batch_with_llm(
                    client,
                    artists=batch,
                    config=config,
                )
            except Exception as exc:
                print(
                    f"Failed batch starting with artist {batch[0]['id']}: {exc}. "
                    "Falling back to one-by-one extraction.",
                    file=sys.stderr,
                )
                for batch_artist in batch:
                    process_one(batch_artist)
                    print(f"Processed {processed} artists; skipped {skipped}; failed {failed}")
                return

            for batch_artist in batch:
                artist_id = int(batch_artist["id"])
                if artist_id not in batch_results:
                    print(
                        f"Batch omitted artist {batch_artist['id']} {batch_artist['name']}; "
                        "falling back to one-by-one extraction.",
                        file=sys.stderr,
                    )
                    process_one(batch_artist)
                    print(f"Processed {processed} artists; skipped {skipped}; failed {failed}")
                    continue

                write_artist_tags(batch_artist, batch_results[artist_id])

            print(f"Processed {processed} artists; skipped {skipped}; failed {failed}")

        pending_batch: list[dict] = []

        for artist in artists:
            text_hash = tag_extraction_text_hash(artist["biography"])
            if not args.force and has_current_artist_tag_extraction(
                connection,
                artist_id=artist["id"],
                source=SOURCE,
                extractor=config.extractor_key,
                text_hash=text_hash,
            ):
                skipped += 1
                continue

            artist["_text_hash"] = text_hash
            pending_batch.append(artist)
            if len(pending_batch) >= args.batch_size:
                process_batch(pending_batch)
                pending_batch = []

        process_batch(pending_batch)

    print(
        f"Artist tag extraction complete with extractor={config.extractor_key}; "
        f"processed={processed}; skipped={skipped}; failed={failed}"
    )


if __name__ == "__main__":
    main()
