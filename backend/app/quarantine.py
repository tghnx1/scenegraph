from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from app.ingestion_quarantine import fetch_unresolved_quarantine


BACKEND_ROOT = Path(__file__).resolve().parents[1]
RETRY_TARGETS = {
    ("artist", "extract_artist_tags"): ("scripts/extract_artist_tags.py", "--artist-id"),
    ("event", "extract_event_tags"): ("scripts/extract_event_tags.py", "--event-id"),
}


def build_retry_command(
    entity_type: str,
    entity_id: int,
    stage: str,
    *,
    dry_run: bool = False,
) -> list[str]:
    target = RETRY_TARGETS.get((entity_type, stage))
    if target is None:
        raise RuntimeError(f"Unsupported quarantine retry target: {entity_type}/{stage}")
    script, id_flag = target
    command = [
        sys.executable,
        str(BACKEND_ROOT / script),
        id_flag,
        str(entity_id),
        "--force",
    ]
    if dry_run:
        command.append("--dry-run")
    return command


def retry_quarantine_item(
    entity_type: str,
    entity_id: int,
    stage: str,
    *,
    dry_run: bool = False,
    run_command=None,
) -> None:
    runner = run_command or subprocess.run
    runner(
        build_retry_command(entity_type, entity_id, stage, dry_run=dry_run),
        cwd=BACKEND_ROOT.parent,
        check=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect and retry ingestion quarantine items.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("list", "retry"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--entity-type", choices=("event", "artist"))
        subparser.add_argument("--stage")
        subparser.add_argument("--entity-id", type=int)
        subparser.add_argument("--limit", type=int, default=100)
        if command == "retry":
            subparser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _load_items(args: argparse.Namespace) -> list[dict]:
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set")
    return fetch_unresolved_quarantine(
        database_url,
        entity_type=args.entity_type,
        stage=args.stage,
        entity_id=args.entity_id,
        limit=args.limit,
    )


def list_items(args: argparse.Namespace) -> int:
    items = _load_items(args)
    for item in items:
        print(json.dumps(item, default=str, ensure_ascii=False))
    print(f"Unresolved quarantine items: {len(items)}", file=sys.stderr)
    return 0


def retry_items(args: argparse.Namespace) -> int:
    items = _load_items(args)
    for item in items:
        retry_quarantine_item(
            str(item["entity_type"]),
            int(item["entity_id"]),
            str(item["stage"]),
            dry_run=args.dry_run,
        )
    print(f"Retried quarantine items: {len(items)}", file=sys.stderr)
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "list":
        return list_items(args)
    return retry_items(args)


if __name__ == "__main__":
    raise SystemExit(main())
