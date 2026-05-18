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
    create_chat_client,
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
        if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
            raise SystemExit("AZURE_OPENAI_ENDPOINT must be set for Azure tag extraction")


def main() -> None:
    args = parse_args()
    config = TagExtractionConfig.from_env()
    ensure_provider_env(config)

    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1")

    client = create_chat_client(config)
    processed = 0
    skipped = 0
    failed = 0

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        artists = fetch_artist_biographies(
            connection,
            artist_id=args.artist_id,
            limit=args.limit,
        )

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
                continue

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
                    text_hash=text_hash,
                    tags=tags,
                )
                connection.commit()

            processed += 1
            print(f"Processed {processed} artists; skipped {skipped}; failed {failed}")

    print(
        f"Artist tag extraction complete with extractor={config.extractor_key}; "
        f"processed={processed}; skipped={skipped}; failed={failed}"
    )


if __name__ == "__main__":
    main()
