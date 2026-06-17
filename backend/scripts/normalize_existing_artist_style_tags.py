from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.style_tags import canonicalize_style_tags, suppress_parent_style_tags


CLEANUP_EXTRACTOR = "canonical_style_cleanup_v1"
CLEANUP_SOURCE = "biography"


@dataclass(frozen=True)
class CanonicalStyleRow:
    artist_id: int
    tag_value: str
    confidence: float
    evidence: str | None


@dataclass(frozen=True)
class ArtistStylePlan:
    artist_id: int
    canonical_rows: tuple[CanonicalStyleRow, ...]
    original_values: tuple[str, ...]
    rejected_values: tuple[str, ...]


def prefer_candidate(candidate: CanonicalStyleRow, existing: CanonicalStyleRow) -> bool:
    return candidate.confidence > existing.confidence or (
        candidate.confidence == existing.confidence
        and existing.evidence is None
        and candidate.evidence is not None
    )


def build_style_cleanup_plan(rows: list[dict]) -> list[ArtistStylePlan]:
    by_artist: dict[int, list[dict]] = {}
    for row in rows:
        by_artist.setdefault(int(row["artist_id"]), []).append(row)

    plans: list[ArtistStylePlan] = []
    for artist_id, artist_rows in sorted(by_artist.items()):
        canonical_by_value: dict[str, CanonicalStyleRow] = {}
        original_values: list[str] = []
        rejected_values: list[str] = []
        for row in artist_rows:
            original = str(row["tag_value"])
            original_values.append(original)
            canonical_values = canonicalize_style_tags(original)
            if not canonical_values:
                rejected_values.append(original)
                continue
            for canonical in canonical_values:
                candidate = CanonicalStyleRow(
                    artist_id=artist_id,
                    tag_value=canonical,
                    confidence=float(row["confidence"]),
                    evidence=row.get("evidence"),
                )
                existing = canonical_by_value.get(canonical)
                if existing is None or prefer_candidate(candidate, existing):
                    canonical_by_value[canonical] = candidate

        retained_values = suppress_parent_style_tags(canonical_by_value)
        plans.append(
            ArtistStylePlan(
                artist_id=artist_id,
                canonical_rows=tuple(
                    canonical_by_value[value] for value in retained_values
                ),
                original_values=tuple(original_values),
                rejected_values=tuple(rejected_values),
            )
        )
    return plans


def fetch_existing_style_rows(connection: Connection) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT artist_id, tag_value, confidence, evidence
            FROM artist_extracted_tags
            WHERE tag_type = 'style'
            ORDER BY artist_id ASC, id ASC
            """
        )
        return cursor.fetchall()


def apply_style_cleanup(connection: Connection, plans: list[ArtistStylePlan]) -> None:
    with connection.cursor() as cursor:
        for plan in plans:
            cursor.execute(
                """
                DELETE FROM artist_extracted_tags
                WHERE artist_id = %s
                  AND tag_type = 'style'
                """,
                (plan.artist_id,),
            )
            for row in plan.canonical_rows:
                cursor.execute(
                    """
                    INSERT INTO artist_extracted_tags (
                        artist_id, tag_type, tag_value, source, confidence, extractor, evidence
                    )
                    VALUES (%s, 'style', %s, %s, %s, %s, %s)
                    """,
                    (
                        row.artist_id,
                        row.tag_value,
                        CLEANUP_SOURCE,
                        row.confidence,
                        CLEANUP_EXTRACTOR,
                        row.evidence,
                    ),
                )


def execute_style_cleanup(
    connection: Connection,
    plans: list[ArtistStylePlan],
    *,
    apply: bool,
) -> None:
    if apply:
        with connection.transaction():
            apply_style_cleanup(connection, plans)


def print_audit(plans: list[ArtistStylePlan]) -> None:
    original_counts = Counter(value for plan in plans for value in plan.original_values)
    canonical_counts = Counter(row.tag_value for plan in plans for row in plan.canonical_rows)
    rejected_counts = Counter(value for plan in plans for value in plan.rejected_values)

    for plan in plans:
        replacements = [
            {
                "originalValue": value,
                "canonicalValues": canonicalize_style_tags(value),
            }
            for value in plan.original_values
        ]
        print(
            json.dumps(
                {
                    "artistId": plan.artist_id,
                    "originalValues": list(plan.original_values),
                    "replacements": replacements,
                    "canonicalValues": [row.tag_value for row in plan.canonical_rows],
                    "rejectedUnknownValues": list(plan.rejected_values),
                },
                ensure_ascii=False,
            )
        )

    print(json.dumps({"originalValueCounts": original_counts.most_common()}, ensure_ascii=False))
    print(json.dumps({"canonicalValueCounts": canonical_counts.most_common()}, ensure_ascii=False))
    print(json.dumps({"rejectedUnknownCounts": rejected_counts.most_common()}, ensure_ascii=False))
    print(
        json.dumps(
            {
                "drumAndBassVariants": [
                    [value, count]
                    for value, count in original_counts.most_common()
                    if canonicalize_style_tags(value) == ["drum and bass"]
                ]
            },
            ensure_ascii=False,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit or explicitly normalize existing artist style tags."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Report changes without writing.")
    mode.add_argument("--apply", action="store_true", help="Apply style-only cleanup in one transaction.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_url = os.environ["DATABASE_URL"]
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        plans = build_style_cleanup_plan(fetch_existing_style_rows(connection))
        print_audit(plans)
        execute_style_cleanup(connection, plans, apply=args.apply)
        if args.apply:
            print(f"Applied canonical style cleanup for {len(plans)} artists.", file=sys.stderr)
        else:
            connection.rollback()
            print("Dry run only; no rows changed.", file=sys.stderr)


if __name__ == "__main__":
    main()
