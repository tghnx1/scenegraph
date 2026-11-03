"""Read-only quality report for a frozen, reviewed promoter-role dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

import psycopg

from app.event_tag_extraction import EventTagExtractionConfig
from app.promoter_role_backfill import extraction_config_hash
from app.promoter_role_evaluation_db import ReviewedCase, evaluate_current_cases, record_quality_review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--record-review", action="store_true", help="Record a completed representative quality review")
    parser.add_argument("--reviewer", help="Name or identifier of the person who reviewed the labels")
    args = parser.parse_args()
    if args.record_review and not args.reviewer:
        parser.error("--record-review requires --reviewer")
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("cases"), list):
        parser.error("manifest must contain a cases array")
    cases: list[ReviewedCase] = []
    seen: set[tuple[str, str]] = set()
    for item in manifest["cases"]:
        if not isinstance(item, dict) or not isinstance(item.get("expected_organizer"), bool):
            parser.error("each case must have a boolean expected_organizer")
        event_id, promoter_id = item.get("ra_event_id"), item.get("ra_promoter_id")
        if not isinstance(event_id, str) or not event_id.isdigit() or not isinstance(promoter_id, str) or not promoter_id.isdigit():
            parser.error("case IDs must be numeric strings")
        if (event_id, promoter_id) in seen:
            parser.error("duplicate reviewed link")
        seen.add((event_id, promoter_id))
        cases.append(ReviewedCase(event_id, promoter_id, item["expected_organizer"]))
    config = EventTagExtractionConfig.from_env()
    current_hash = extraction_config_hash(config)
    review_id = None
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        if not args.record_review:
            connection.execute("SET TRANSACTION READ ONLY")
        report = evaluate_current_cases(connection, tuple(cases), config_hash=current_hash,
                                        representative=(manifest.get("release_representative") is True
                                                        and manifest.get("frozen_before_model_evaluation") is True))
        if args.record_review:
            review_id = record_quality_review(connection, report, config_hash=current_hash,
                                              manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                                              reviewer=args.reviewer)
    print(json.dumps({"manifest": manifest.get("version"), "quality": asdict(report.quality),
                      "unavailable": report.unavailable, "release_ready": report.release_ready,
                      "review_id": review_id, "cases": [asdict(case) for case in report.cases]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
