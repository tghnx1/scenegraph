#!/usr/bin/env python3

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.event_tag_extraction import (
    EventTagExtractionConfig,
    create_extraction_client,
    event_extraction_hash_input,
    event_source_fields,
    event_tag_extraction_text_hash,
    extract_event_tag_batch_with_llm,
    extract_event_tags_with_chunked_fallback,
    extract_event_tags_with_llm,
    fetch_event_texts,
    has_current_event_tag_extraction,
    replace_event_tags,
)
from app.ingestion_quarantine import (
    classify_extraction_error,
    extraction_error_metadata,
    quarantine_entity,
    resolve_quarantine,
)


DATABASE_URL = os.environ["DATABASE_URL"]
SOURCE = "description"


def load_id_file(path: Path | None) -> list[int] | None:
    if path is None:
        return None
    if not path.exists():
        raise SystemExit(f"ID file not found: {path}")
    ids: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            ids.append(int(raw))
        except ValueError as exc:
            raise SystemExit(f"Invalid integer id in {path}: {raw}") from exc
    return ids


# Formats one extracted event for compact progress logs.
def event_log_label(event: dict) -> str:
    name = str(event.get("name") or "").replace("\n", " ").strip()
    if len(name) > 80:
        name = f"{name[:77]}..."
    return f"{event['id']}:{name}"


# Writes batch-level progress so long extraction runs can be resumed confidently.
def print_batch_progress(
    *,
    batch: list[dict],
    processed: int,
    skipped: int,
    quarantined: int,
    failed: int,
    total: int,
) -> None:
    remaining = max(total - processed - skipped - quarantined - failed, 0)
    labels = ", ".join(event_log_label(event) for event in batch)
    print(
        "Processed event batch "
        f"[{labels}]; processed={processed}; skipped={skipped}; "
        f"quarantined={quarantined}; failed={failed}; remaining={remaining}/{total}",
        file=sys.stderr,
        flush=True,
    )


def event_tags_json_line(event: dict, tags: list, config: EventTagExtractionConfig) -> str:
    return json.dumps(
        {
            "eventId": event["id"],
            "eventName": event["name"],
            "extractor": config.extractor_key,
            "styleNormalization": "source-aware-canonical-style-v3",
            "mode": event.get("_extraction_mode", "full"),
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


def print_completion_summary(
    config: EventTagExtractionConfig,
    *,
    processed: int,
    skipped: int,
    quarantined: int,
    failed: int,
) -> None:
    print(
        f"Event tag extraction complete with extractor={config.extractor_key}; "
        "styles=source-aware-canonical-style-v3; "
        f"processed={processed}; skipped={skipped}; quarantined={quarantined}; failed={failed}",
        file=sys.stderr,
    )


def output_or_persist_event_tags(
    connection,
    *,
    event: dict,
    tags: list,
    config: EventTagExtractionConfig,
    dry_run: bool,
    output=sys.stdout,
) -> None:
    if dry_run:
        print(event_tags_json_line(event, tags, config), file=output)
        return
    replace_event_tags(
        connection,
        event_id=event["id"],
        source=SOURCE,
        extractor=config.extractor_key,
        text_hash=event["_text_hash"],
        tags=tags,
    )
    connection.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract structured event tags from event text with an LLM.")
    parser.add_argument("--event-id", type=int, default=None, help="Extract tags for one event id.")
    parser.add_argument("--after-id", type=int, default=None, help="Only process events with id greater than this.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum events to process.")
    parser.add_argument("--offset", type=int, default=0, help="Skip this many events in deterministic id order.")
    parser.add_argument("--batch-size", type=int, default=1, help="Number of events per LLM request.")
    parser.add_argument("--force", action="store_true", help="Re-extract even if text hash is unchanged.")
    parser.add_argument("--dry-run", action="store_true", help="Print extracted tags without writing to DB.")
    parser.add_argument(
        "--no-chunk-fallback",
        action="store_true",
        help="Disable chunked retry for recoverable full-event extraction failures.",
    )
    parser.add_argument("--continue-on-error", action="store_true", help="Continue when one event fails.")
    parser.add_argument(
        "--event-ids-file",
        type=Path,
        default=None,
        help="Optional newline-delimited list of event ids to process.",
    )
    return parser.parse_args()


def ensure_provider_env(config: EventTagExtractionConfig) -> None:
    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        raise SystemExit("AZURE_OPENAI_API_KEY must be set for Azure tag extraction")


def main() -> None:
    args = parse_args()
    config = EventTagExtractionConfig.from_env()
    ensure_provider_env(config)

    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1")
    if args.after_id is not None and args.after_id < 0:
        raise ValueError("--after-id must be zero or greater")
    if args.offset < 0:
        raise ValueError("--offset must be zero or greater")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")
    if args.event_id is not None and args.batch_size != 1:
        args.batch_size = 1

    client = create_extraction_client()
    processed = 0
    skipped = 0
    quarantined = 0
    failed = 0
    event_ids = load_id_file(args.event_ids_file)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        events = fetch_event_texts(
            connection,
            event_ids=event_ids,
            event_id=args.event_id,
            limit=args.limit,
            offset=args.offset,
            after_id=args.after_id,
        )
        total_events = len(events)

        def quarantine_event(event: dict, error: BaseException, error_type: str) -> None:
            nonlocal quarantined
            attempts: int | None = None
            if not args.dry_run:
                attempts = quarantine_entity(
                    connection,
                    entity_type="event",
                    entity_id=event["id"],
                    stage="extract_event_tags",
                    error=error,
                    metadata=extraction_error_metadata(error),
                )
            quarantined += 1
            attempt_text = f"; attempts={attempts}" if attempts is not None else "; dry_run=true"
            action = "Would quarantine" if args.dry_run else "Quarantined"
            print(
                f"{action} event {event['id']} {event['name']}: "
                f"stage=extract_event_tags; error_type={error_type}{attempt_text}",
                file=sys.stderr,
            )

        def write_event_tags(event: dict, tags: list) -> None:
            nonlocal processed
            output_or_persist_event_tags(
                connection,
                event=event,
                tags=tags,
                config=config,
                dry_run=args.dry_run,
            )
            processed += 1
            if not args.dry_run:
                resolve_quarantine(
                    connection,
                    entity_type="event",
                    entity_id=event["id"],
                    stage="extract_event_tags",
                )

        def process_one(event: dict) -> bool:
            nonlocal failed, quarantined
            try:
                tags = extract_event_tags_with_llm(
                    client,
                    event_name=event["name"],
                    event_text=event["text"],
                    config=config,
                    sources=event_source_fields(event),
                )
            except Exception as exc:
                fallback_reason = classify_extraction_error(exc)
                if not args.no_chunk_fallback and fallback_reason is not None:
                    try:
                        fallback = extract_event_tags_with_chunked_fallback(
                            client,
                            event_name=event["name"],
                            event_text=event["text"],
                            config=config,
                            sources=event_source_fields(event),
                        )
                    except Exception as fallback_exc:
                        fallback_error_type = classify_extraction_error(fallback_exc)
                        if fallback_error_type is not None:
                            quarantine_event(event, fallback_exc, fallback_error_type)
                            return False
                        failed += 1
                        print(
                            f"Failed chunked fallback event {event['id']} {event['name']}: {fallback_exc}",
                            file=sys.stderr,
                        )
                        if not args.continue_on_error:
                            raise
                        return False
                    if fallback.processed_chunks > 0:
                        tags = fallback.tags
                        event["_extraction_mode"] = "chunked_fallback"
                    else:
                        quarantine_event(event, exc, fallback_reason)
                        return False
                else:
                    error_type = classify_extraction_error(exc)
                    if error_type is not None and not args.no_chunk_fallback:
                        quarantine_event(event, exc, error_type)
                        return False
                    failed += 1
                    print(f"Failed event {event['id']} {event['name']}: {exc}", file=sys.stderr)
                    if not args.continue_on_error:
                        raise
                    return False

            write_event_tags(event, tags)
            return True

        def process_batch(batch: list[dict]) -> None:
            before_processed = processed
            before_failed = failed
            if not batch:
                return
            if args.batch_size == 1 or len(batch) == 1:
                for row in batch:
                    process_one(row)
                    print_batch_progress(
                        batch=[row],
                        processed=processed,
                        skipped=skipped,
                        quarantined=quarantined,
                        failed=failed,
                        total=total_events,
                    )
                return
            try:
                batch_results = extract_event_tag_batch_with_llm(client, events=batch, config=config)
            except Exception:
                for row in batch:
                    process_one(row)
                    print_batch_progress(
                        batch=[row],
                        processed=processed,
                        skipped=skipped,
                        quarantined=quarantined,
                        failed=failed,
                        total=total_events,
                    )
                return

            for row in batch:
                event_id = int(row["id"])
                if event_id not in batch_results:
                    process_one(row)
                    continue
                write_event_tags(row, batch_results[event_id])
            if processed != before_processed or failed != before_failed:
                print_batch_progress(
                    batch=batch,
                    processed=processed,
                    skipped=skipped,
                    quarantined=quarantined,
                    failed=failed,
                    total=total_events,
                )

        pending_batch: list[dict] = []
        for event in events:
            text_hash = event_tag_extraction_text_hash(event_extraction_hash_input(event))
            if not args.force and has_current_event_tag_extraction(
                connection,
                event_id=event["id"],
                source=SOURCE,
                extractor=config.extractor_key,
                text_hash=text_hash,
            ):
                skipped += 1
                continue
            event["_text_hash"] = text_hash
            pending_batch.append(event)
            if len(pending_batch) >= args.batch_size:
                process_batch(pending_batch)
                pending_batch = []
        process_batch(pending_batch)

    print_completion_summary(
        config,
        processed=processed,
        skipped=skipped,
        quarantined=quarantined,
        failed=failed,
    )


if __name__ == "__main__":
    main()
