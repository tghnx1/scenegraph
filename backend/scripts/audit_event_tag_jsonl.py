from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.style_tags import STYLE_ALIASES, style_alias_pattern


SUSPICIOUS_PATTERNS = {
    "dnb_audio_brand": re.compile(r"\bd&b\s+audiotechnik\b", re.IGNORECASE),
    "high_energy_hi_nrg": re.compile(r"\bhigh[-\s]+energy\b", re.IGNORECASE),
}


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            invalid.append({"line": number, "error": str(exc)})
            continue
        if isinstance(payload, dict):
            records.append(payload)
        else:
            invalid.append({"line": number, "error": "JSON value is not an object"})
    return records, invalid


def suspicious_tags(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for record in records:
        event_name = str(record.get("eventName") or "")
        for tag in record.get("tags") or []:
            tag_type = str(tag.get("type") or "")
            tag_value = str(tag.get("value") or "")
            evidence = str(tag.get("evidence") or "")
            checks = {
                "dnb_audio_brand": tag_type == "style" and tag_value == "drum and bass",
                "high_energy_hi_nrg": tag_type == "style" and tag_value == "hi-nrg",
            }
            for name, enabled in checks.items():
                if enabled and SUSPICIOUS_PATTERNS[name].search(evidence):
                    findings.append(
                        {
                            "check": name,
                            "eventId": record.get("eventId"),
                            "eventName": event_name,
                            "tag": {"type": tag_type, "value": tag_value, "evidence": evidence},
                        }
                    )
            if tag_type == "style" and re.search(
                rf"\b(?:break\s+from|not|no|without|instead\s+of|alternative\s+to|far\s+from|anything\s+but)"
                rf"\s+{re.escape(tag_value)}\b",
                evidence,
                re.IGNORECASE,
            ):
                findings.append(
                    {
                        "check": "negated_style",
                        "eventId": record.get("eventId"),
                        "eventName": event_name,
                        "tag": {"type": tag_type, "value": tag_value, "evidence": evidence},
                    }
                )
            if tag_type == "series" and re.search(
                rf"\bhosted\s+by\s+{re.escape(tag_value)}\b"
                rf"|\b{re.escape(tag_value)}\s+presents?\b"
                rf"|(?:@|\bat\b|\bvenue:|\blocation:)\s*{re.escape(tag_value)}\b",
                evidence,
                re.IGNORECASE,
            ):
                findings.append(
                    {
                        "check": "host_or_venue_series",
                        "eventId": record.get("eventId"),
                        "eventName": event_name,
                        "tag": {"type": tag_type, "value": tag_value, "evidence": evidence},
                    }
                )
            if tag_type == "style" and evidence.startswith(("title:", "lineup:")):
                if re.search(rf"(?<!\w){re.escape(tag_value)}(?!\w)", event_name, re.IGNORECASE):
                    findings.append(
                        {
                            "check": "possible_artist_name_style",
                            "eventId": record.get("eventId"),
                            "eventName": event_name,
                            "tag": {"type": tag_type, "value": tag_value, "evidence": evidence},
                        }
                    )
            if tag_type == "style" and tag_value in STYLE_ALIASES:
                evidence_text = evidence.split(":", 1)[-1]
                if not any(
                    style_alias_pattern(alias).search(evidence_text)
                    for alias in STYLE_ALIASES[tag_value]
                ):
                    findings.append(
                        {
                            "check": "unicode_substring_style_match",
                            "eventId": record.get("eventId"),
                            "eventName": event_name,
                            "tag": {"type": tag_type, "value": tag_value, "evidence": evidence},
                        }
                    )
    return findings


def audit_records(
    records: list[dict[str, Any]],
    *,
    invalid_lines: list[dict[str, Any]] | None = None,
    max_tags: int = 12,
) -> dict[str, Any]:
    invalid_lines = invalid_lines or []
    tags = [tag for record in records for tag in (record.get("tags") or [])]
    type_counts = Counter(str(tag.get("type") or "") for tag in tags)
    canonical_counts = {
        tag_type: dict(sorted(Counter(
            str(tag.get("value") or "")
            for tag in tags
            if tag.get("type") == tag_type
        ).items()))
        for tag_type in sorted(type_counts)
    }
    canonical_pairs = Counter(
        (str(tag.get("type") or ""), str(tag.get("value") or "")) for tag in tags
    )
    source_counts = Counter(
        str(tag.get("evidence") or "").split(":", 1)[0]
        if ":" in str(tag.get("evidence") or "")
        else "unprefixed"
        for tag in tags
    )
    return {
        "validJsonLines": len(records),
        "invalidJsonLines": invalid_lines,
        "eventCount": len(records),
        "totalTagCount": len(tags),
        "tagsPerType": dict(sorted(type_counts.items())),
        "uniqueTypeValueCount": len(canonical_pairs),
        "singletonTypeValueCount": sum(count == 1 for count in canonical_pairs.values()),
        "maximumTagsPerEvent": max((len(record.get("tags") or []) for record in records), default=0),
        "eventsExceedingMaximum": [
            record.get("eventId")
            for record in records
            if len(record.get("tags") or []) > max_tags
        ],
        "zeroTagEvents": [
            {"eventId": record.get("eventId"), "eventName": record.get("eventName")}
            for record in records
            if not record.get("tags")
        ],
        "tagsWithoutEvidence": [
            {"eventId": record.get("eventId"), "tag": tag}
            for record in records
            for tag in (record.get("tags") or [])
            if not tag.get("evidence")
        ],
        "extractorVersions": dict(sorted(Counter(
            str(record.get("extractor") or "") for record in records
        ).items())),
        "evidenceSourceCounts": dict(sorted(source_counts.items())),
        "canonicalValueCountsByType": canonical_counts,
        "suspiciousFindings": suspicious_tags(records),
    }


def compare_records(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> dict[str, Any]:
    before_by_id = {record.get("eventId"): record for record in before}
    after_by_id = {record.get("eventId"): record for record in after}
    event_ids = sorted(set(before_by_id) | set(after_by_id), key=lambda value: (value is None, value))

    def tag_set(record: dict[str, Any] | None) -> set[tuple[str, str]]:
        return {
            (str(tag.get("type") or ""), str(tag.get("value") or ""))
            for tag in ((record or {}).get("tags") or [])
        }

    changes = []
    for event_id in event_ids:
        before_tags = tag_set(before_by_id.get(event_id))
        after_tags = tag_set(after_by_id.get(event_id))
        if before_tags != after_tags:
            changes.append(
                {
                    "eventId": event_id,
                    "added": sorted(after_tags - before_tags),
                    "removed": sorted(before_tags - after_tags),
                }
            )
    return {
        "eventsWithChanges": changes,
        "newlyEmptyEvents": sorted(
            event_id
            for event_id in event_ids
            if tag_set(before_by_id.get(event_id)) and not tag_set(after_by_id.get(event_id))
        ),
        "eventsNoLongerEmpty": sorted(
            event_id
            for event_id in event_ids
            if not tag_set(before_by_id.get(event_id)) and tag_set(after_by_id.get(event_id))
        ),
        "aggregateDifferences": {
            "eventCount": len(after) - len(before),
            "totalTagCount": sum(len(record.get("tags") or []) for record in after)
            - sum(len(record.get("tags") or []) for record in before),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit event-tag dry-run JSONL files without modifying them.")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--max-tags", type=int, default=12)
    args = parser.parse_args()
    if len(args.files) > 2:
        parser.error("provide one or two JSONL files")

    loaded = [load_jsonl(path) for path in args.files]
    report = {
        "files": {
            str(path): audit_records(records, invalid_lines=invalid, max_tags=args.max_tags)
            for path, (records, invalid) in zip(args.files, loaded)
        }
    }
    if len(loaded) == 2:
        report["comparison"] = compare_records(loaded[0][0], loaded[1][0])
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
