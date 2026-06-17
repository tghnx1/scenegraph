#!/usr/bin/env python3

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
    extract_artist_tags_with_chunked_fallback,
    extract_artist_tags_with_llm,
    fetch_artist_biographies,
    has_current_artist_tag_extraction,
    is_content_filter_error,
    replace_artist_tags,
    tag_extraction_text_hash,
)


DATABASE_URL = os.environ["DATABASE_URL"]
SOURCE = "biography"


# Formats one extracted artist for compact progress logs.
def artist_log_label(artist: dict) -> str:
    name = str(artist.get("name") or "").replace("\n", " ").strip()
    if len(name) > 80:
        name = f"{name[:77]}..."
    return f"{artist['id']}:{name}"


# Writes batch-level progress so long extraction runs can be resumed confidently.
def print_batch_progress(
    *,
    batch: list[dict],
    processed: int,
    skipped: int,
    failed: int,
    total: int,
) -> None:
    remaining = max(total - processed - skipped - failed, 0)
    labels = ", ".join(artist_log_label(artist) for artist in batch)
    print(
        "Processed artist batch "
        f"[{labels}]; processed={processed}; skipped={skipped}; "
        f"failed={failed}; remaining={remaining}/{total}",
        file=sys.stderr,
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract structured artist tags from biographies with an LLM.")
    parser.add_argument("--artist-id", type=int, default=None, help="Extract tags for one artist id.")
    parser.add_argument("--after-id", type=int, default=None, help="Only process artists with id greater than this.")
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
        "--no-chunk-fallback",
        action="store_true",
        help="Disable chunked retry when the provider blocks a full biography with content_filter.",
    )
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
    if args.after_id is not None and args.after_id < 0:
        raise ValueError("--after-id must be zero or greater")
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
            after_id=args.after_id,
        )
        total_artists = len(artists)

        def write_artist_tags(artist: dict, tags: list) -> None:
            nonlocal processed
            if args.dry_run:
                output = {
                    "artistId": artist["id"],
                    "artistName": artist["name"],
                    "extractor": config.extractor_key,
                    "styleNormalization": "canonical-style-v2",
                    "mode": artist.get("_extraction_mode", "full"),
                    "tags": [
                        {
                            "type": tag.tag_type,
                            "value": tag.tag_value,
                            "confidence": tag.confidence,
                            "evidence": tag.evidence,
                        }
                        for tag in tags
                    ],
                }
                if "_chunk_fallback" in artist:
                    output["chunkFallback"] = artist["_chunk_fallback"]
                print(json.dumps(output, ensure_ascii=False))
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
                if not args.no_chunk_fallback and is_content_filter_error(exc):
                    try:
                        fallback = extract_artist_tags_with_chunked_fallback(
                            client,
                            artist_name=artist["name"],
                            biography=artist["biography"],
                            config=config,
                        )
                    except Exception as fallback_exc:
                        failed += 1
                        print(
                            f"Failed chunked fallback artist {artist['id']} {artist['name']}: "
                            f"{fallback_exc}",
                            file=sys.stderr,
                        )
                        if not args.continue_on_error:
                            raise
                        return False

                    if fallback.processed_chunks > 0:
                        tags = fallback.tags
                        artist["_extraction_mode"] = "chunked_fallback"
                        artist["_chunk_fallback"] = {
                            "totalChunks": fallback.total_chunks,
                            "processedChunks": fallback.processed_chunks,
                            "skippedChunks": fallback.skipped_chunks,
                        }
                        print(
                            f"Chunked fallback artist {artist['id']} {artist['name']}: "
                            f"processed_chunks={fallback.processed_chunks}/"
                            f"{fallback.total_chunks}; skipped_chunks={fallback.skipped_chunks}; "
                            f"tags={len(tags)}",
                            file=sys.stderr,
                        )
                    else:
                        failed += 1
                        print(
                            f"Failed artist {artist['id']} {artist['name']}: "
                            "all biography chunks were blocked by content_filter",
                            file=sys.stderr,
                        )
                        if not args.continue_on_error:
                            raise
                        return False
                else:
                    failed += 1
                    print(f"Failed artist {artist['id']} {artist['name']}: {exc}", file=sys.stderr)
                    if not args.continue_on_error:
                        raise
                    return False

            write_artist_tags(artist, tags)
            return True

        def process_batch(batch: list[dict]) -> None:
            nonlocal failed
            before_processed = processed
            before_failed = failed
            if not batch:
                return

            if args.batch_size == 1 or len(batch) == 1:
                for batch_artist in batch:
                    process_one(batch_artist)
                    print_batch_progress(
                        batch=[batch_artist],
                        processed=processed,
                        skipped=skipped,
                        failed=failed,
                        total=total_artists,
                    )
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
                    print_batch_progress(
                        batch=[batch_artist],
                        processed=processed,
                        skipped=skipped,
                        failed=failed,
                        total=total_artists,
                    )
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
                    print_batch_progress(
                        batch=[batch_artist],
                        processed=processed,
                        skipped=skipped,
                        failed=failed,
                        total=total_artists,
                    )
                    continue

                write_artist_tags(batch_artist, batch_results[artist_id])

            if processed != before_processed or failed != before_failed:
                print_batch_progress(
                    batch=batch,
                    processed=processed,
                    skipped=skipped,
                    failed=failed,
                    total=total_artists,
                )

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
        "styles=canonical-style-v2; "
        f"processed={processed}; skipped={skipped}; failed={failed}"
    )


if __name__ == "__main__":
    main()
