"""Bounded promoter-role backfill; dry-run is the default."""

from __future__ import annotations

import argparse
import json
import os

import psycopg

from app.event_tag_extraction import EventTagExtractionConfig
from app.promoter_role_backfill import MAX_EVENTS, config_hash, create_run, process_run
from app.promoter_role_store import load_event_input
from app.promoter_roles import DESCRIPTION_LIMIT, role_input_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--event-id", type=int, action="append", help="Internal event ID; repeat for each event")
    scope.add_argument("--resume-run", type=int)
    parser.add_argument("--apply", action="store_true", help="Persist and process a bounded run")
    args = parser.parse_args()
    if args.resume_run is not None and not args.apply:
        parser.error("--resume-run requires --apply")
    if args.event_id and (len(args.event_id) > MAX_EVENTS or len(set(args.event_id)) != len(args.event_id)):
        parser.error("provide at most 1000 unique event IDs")
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        if not args.apply:
            connection.execute("SET TRANSACTION READ ONLY")
            for event_id in args.event_id:
                source = load_event_input(connection, event_id)
                if source is None:
                    raise SystemExit(f"event {event_id} not found")
                # Conservative size estimate, not actual provider token usage.
                chars = len(source.title) + len((source.description or "")[:DESCRIPTION_LIMIT])
                print(json.dumps({"event_id": event_id, "input_hash": role_input_hash(source),
                                  "promoter_count": len(source.promoters), "input_characters": chars,
                                  "estimated_text_tokens": (chars + 3) // 4}, ensure_ascii=False))
            return 0
        config = EventTagExtractionConfig.from_env()
        current_hash = config_hash(config.provider, config.model, config.reasoning_effort)
        run_id = args.resume_run
        if run_id is None:
            run_id = create_run(connection, tuple(args.event_id), current_hash)
            connection.commit()
        print(f"run_id={run_id}", flush=True)
        status = process_run(connection, run_id, current_hash)
        print(f"status={status}")
        return 0 if status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
