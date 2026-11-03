"""Compare existing and role-filtered recommendations for one explicitly selected artist."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Callable

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.event_tag_extraction import EventTagExtractionConfig
from app.promoter_role_backfill import extraction_config_hash
from app.promoter_role_relation import role_filtered_relation
from app.promoter_roles import CLASSIFIER_VERSION
from app.recommendations.services import build_artist_promoter_recommendation_response
from app.schemas import PromoterRecommendationResponse


@dataclass(frozen=True, slots=True)
class ShadowComparison:
    baseline_ids: tuple[int, ...]
    shadow_ids: tuple[int, ...]

    @property
    def removed_ids(self) -> tuple[int, ...]:
        return tuple(value for value in self.baseline_ids if value not in self.shadow_ids)

    @property
    def added_ids(self) -> tuple[int, ...]:
        return tuple(value for value in self.shadow_ids if value not in self.baseline_ids)


def compare_recommendations(
    connection: psycopg.Connection, *, artist_id: int, user_id: int, limit: int,
    current_config_hash: str,
    builder: Callable[..., PromoterRecommendationResponse] = build_artist_promoter_recommendation_response,
) -> ShadowComparison:
    """Run the unchanged engine twice; return the normal result separately from shadow."""
    baseline = builder(connection, artist_id=artist_id, user_id=user_id, limit=limit, debug=False)
    with role_filtered_relation(connection, current_config_hash):
        shadow = builder(connection, artist_id=artist_id, user_id=user_id, limit=limit, debug=False)
    return ShadowComparison(tuple(item.id for item in baseline.recommendations),
                            tuple(item.id for item in shadow.recommendations))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artist-id", type=int, required=True)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--persist", action="store_true", help="Store both result ID lists separately")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    config = EventTagExtractionConfig.from_env()
    current_hash = extraction_config_hash(config)
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as connection:
        result = compare_recommendations(connection, artist_id=args.artist_id, user_id=args.user_id,
                                         limit=args.limit, current_config_hash=current_hash)
        if args.persist:
            connection.execute("""
                INSERT INTO promoter_role_shadow_result
                  (artist_id, user_id, config_hash, classifier_version, baseline, shadow)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (args.artist_id, args.user_id, current_hash, CLASSIFIER_VERSION,
                  Jsonb(list(result.baseline_ids)), Jsonb(list(result.shadow_ids))))
        else:
            connection.rollback()
        print(json.dumps({"baseline": result.baseline_ids, "shadow": result.shadow_ids,
                          "removed": result.removed_ids, "added": result.added_ids}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
