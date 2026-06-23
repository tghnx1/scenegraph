from __future__ import annotations

import logging
import math

from fastapi import HTTPException
from psycopg import Connection

from app.event_similarity import artist_similar_events_scored_rows
from app.promoter_graph import (
    date_recency_score,
    promoter_direct_connection_evidence,
    promoter_manual_connection_evidence,
    promoter_recommendation_evidence,
    promoter_recommendation_graph,
    promoter_recommendation_item_evidence,
    promoter_recommendation_reasons,
    promoter_recommendation_status,
    project_compact_recommendation_graph,
    promoter_warm_network_evidence,
)
from app.promoter_feedback import (
    apply_promoter_feedback_reranking,
    load_promoter_feedback,
    load_promoter_content_profiles,
    promoter_content_similarities,
    promoter_feedback_config_from_env,
)
from app.recommendation_engine import (
    apply_artist_indirect_features,
    recommendation_feature_sets,
)
from app.recommendation_helpers import (
    artist_semantic_metadata,
    build_artist_semantic_candidates,
    load_promoter_style_sources,
    promoter_style_candidate_ids,
    recommendation_item_metadata,
    shared_tag_values,
)
from app.recommendation_scoring import (
    DEFAULT_RECOMMENDATION_SCORING,
    artist_recommendation_min_semantic_score_from_env,
    final_recommendation_score,
    hybrid_graph_score,
    promoter_segment_quota_ratios_from_env,
    promoter_segment_warm_share_from_env,
    promoter_recommendation_matching_mode_from_env,
    promoter_recommendation_scoring_from_env,
)
from app.style_tags import style_overlap_score
from app.schemas import (
    GraphResponse,
    PromoterRecommendationItem,
    PromoterRecommendationResponse,
    SemanticArtistItem,
    SemanticArtistResponse,
)

logger = logging.getLogger(__name__)

# Keep warm/manual recommendations in the top score band so score-only sorting
# naturally places them above discovery recommendations.
def promoter_recommendation_adjusted_score(base_score: float, *, has_warm_path: bool) -> float:
    bounded_base_score = max(0.0, min(float(base_score), 1.0))
    if has_warm_path:
        return 0.5 + 0.5 * bounded_base_score
    return 0.5 * bounded_base_score

# Build short explanation strings for semantic artist matches.
def semantic_artist_reasons(item: dict) -> list[str]:
    """Build short human-readable reasons for artist-to-artist semantic similarity."""
    reasons = []
    shared_styles = item["shared_styles"]
    shared_tags = item["shared_tags"]
    if shared_styles:
        reasons.append(f"{len(shared_styles)} shared styles: {', '.join(shared_styles[:5])}")

    for tag_type in ("label", "collective", "residency"):
        values = shared_tags.get(tag_type, [])
        if values:
            reasons.append(f"{len(values)} shared {tag_type} tags: {', '.join(values[:3])}")

    if item["embedding_score"] >= 0.60:
        reasons.append("semantic profile match")
    if not reasons:
        reasons.append("semantic similarity")
    return reasons[:3]

# Read source artist scale statistics used by size-fit scoring.
def source_artist_scale_stats(connection: Connection, *, artist_id: int) -> dict[str, int | float | None]:
    """Return source artist scale stats used for promoter size-fit normalization."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH source_events AS (
                SELECT DISTINCT event_id
                FROM event_artists
                WHERE artist_id = %s
            ),
            source_scales AS (
                SELECT
                    count(*)::int AS event_count
                FROM source_events
            ),
            source_interested AS (
                SELECT
                    avg(e.interested_count)::double precision AS avg_interested,
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY e.interested_count)::double precision
                        AS median_interested
                FROM source_events se
                JOIN events e
                    ON e.id = se.event_id
                WHERE e.interested_count IS NOT NULL
            )
            SELECT ss.event_count, si.avg_interested, si.median_interested
            FROM source_scales ss
            CROSS JOIN source_interested si
            """,
            (artist_id,),
        )
        row = cursor.fetchone()
    if row is None:
        return {"event_count": 0, "avg_interested": None, "median_interested": None}
    return row

# Convert source/promoter scale ratio into a smooth fit score.
def scale_fit_score(
    *,
    artist_scale: float,
    promoter_scale: float,
    alpha: float,
    tau: float,
) -> float:
    """Score how close promoter scale is to source-artist scale in log-ratio space."""
    ratio = (promoter_scale + alpha) / (artist_scale + alpha)
    return math.exp(-abs(math.log(ratio)) / tau)

# Map event volume into coarse scale buckets.
def scale_bucket(event_count: int) -> int:
    """
    Coarse promoter scale buckets by related event volume.
    0 = small, 1 = medium, 2 = large.
    """
    if event_count <= 3:
        return 0
    if event_count <= 12:
        return 1
    return 2

# Penalize bucket distance between source artist and promoter scale.
def scale_bucket_match_multiplier(source_event_count: int, promoter_event_count: int) -> float:
    """Convert discrete source/promoter bucket distance into a multiplicative penalty."""
    distance = abs(scale_bucket(source_event_count) - scale_bucket(promoter_event_count))
    if distance == 0:
        return 1.0
    if distance == 1:
        return 0.65
    return 0.30


def interested_tertile_thresholds(values: list[int]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    sorted_values = sorted(float(value) for value in values)
    if len(sorted_values) == 1:
        return sorted_values[0], sorted_values[0]

    def percentile(percent: float) -> float:
        index = (len(sorted_values) - 1) * percent
        lower_index = math.floor(index)
        upper_index = math.ceil(index)
        if lower_index == upper_index:
            return sorted_values[lower_index]
        ratio = index - lower_index
        return (
            sorted_values[lower_index]
            + (sorted_values[upper_index] - sorted_values[lower_index]) * ratio
        )

    return percentile(1.0 / 3.0), percentile(2.0 / 3.0)


# Compute distribution thresholds for artist size segmentation by average interested count.
def artist_interest_segment_thresholds(connection: Connection) -> tuple[float, float]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH artist_interest AS (
                SELECT
                    ea.artist_id,
                    avg(e.interested_count)::double precision AS avg_interested
                FROM event_artists ea
                JOIN events e
                    ON e.id = ea.event_id
                WHERE e.interested_count IS NOT NULL
                GROUP BY ea.artist_id
            )
            SELECT
                COALESCE(percentile_cont(0.333333) WITHIN GROUP (ORDER BY avg_interested), 0)::double precision
                    AS low_threshold,
                COALESCE(percentile_cont(0.666667) WITHIN GROUP (ORDER BY avg_interested), 0)::double precision
                    AS high_threshold
            FROM artist_interest
            """
        )
        row = cursor.fetchone()
    if row is None:
        return 0.0, 0.0
    return float(row["low_threshold"]), float(row["high_threshold"])


# Map an interested metric into small/medium/large segment.
def interest_segment_label(value: float | int | None, *, low_threshold: float, high_threshold: float) -> str:
    if value is None:
        return "small"
    numeric_value = float(value)
    if numeric_value <= low_threshold:
        return "small"
    if numeric_value <= high_threshold:
        return "medium"
    return "large"


def promoter_segment_sort_order(source_artist_size_segment: str) -> tuple[str, str, str]:
    """Return segment priority order aligned with source artist size segment."""
    if source_artist_size_segment == "small":
        return ("small", "medium", "large")
    if source_artist_size_segment == "medium":
        return ("medium", "large", "small")
    return ("large", "medium", "small")


def segment_quota_counts(
    *,
    limit: int,
    segment_order: tuple[str, str, str],
    segment_ratios: dict[str, float],
) -> dict[str, int]:
    """Convert segment ratios into integer quota counts with deterministic remainder distribution."""
    raw_quota = {
        segment: float(limit) * max(float(segment_ratios.get(segment, 0.0)), 0.0)
        for segment in segment_order
    }
    quota_counts = {segment: int(math.floor(value)) for segment, value in raw_quota.items()}
    assigned = sum(quota_counts.values())
    remainder = max(limit - assigned, 0)
    segment_by_fraction = sorted(
        segment_order,
        key=lambda segment: (-(raw_quota[segment] - quota_counts[segment]), segment_order.index(segment)),
    )
    for segment in segment_by_fraction[:remainder]:
        quota_counts[segment] += 1
    return quota_counts


# Resolve shared artists for concrete source-event and candidate-event pairs.
def event_similarity_shared_artists_by_pair(
    connection: Connection,
    *,
    source_artist_id: int,
    event_pairs: list[tuple[int, int]],
) -> dict[tuple[int, int], list[dict[str, object]]]:
    if not event_pairs:
        return {}

    source_event_ids = [source_event_id for source_event_id, _ in event_pairs]
    candidate_event_ids = [candidate_event_id for _, candidate_event_id in event_pairs]

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH requested_pairs AS (
                SELECT *
                FROM unnest(%(source_event_ids)s::bigint[], %(candidate_event_ids)s::bigint[])
                    AS pair(source_event_id, candidate_event_id)
            )
            SELECT
                pair.source_event_id,
                pair.candidate_event_id,
                a.id AS artist_id,
                a.name AS artist_name
            FROM requested_pairs pair
            JOIN event_artists ea_source
                ON ea_source.event_id = pair.source_event_id
            JOIN event_artists ea_candidate
                ON ea_candidate.event_id = pair.candidate_event_id
               AND ea_candidate.artist_id = ea_source.artist_id
            JOIN artists a
                ON a.id = ea_source.artist_id
            WHERE ea_source.artist_id <> %(source_artist_id)s
            ORDER BY pair.source_event_id ASC, pair.candidate_event_id ASC, a.name ASC
            """,
            {
                "source_event_ids": source_event_ids,
                "candidate_event_ids": candidate_event_ids,
                "source_artist_id": source_artist_id,
            },
        )
        rows = cursor.fetchall()

    result: dict[tuple[int, int], list[dict[str, object]]] = {}
    for row in rows:
        source_event_id = int(row["source_event_id"] if isinstance(row, dict) else row[0])
        candidate_event_id = int(row["candidate_event_id"] if isinstance(row, dict) else row[1])
        artist_id = int(row["artist_id"] if isinstance(row, dict) else row[2])
        artist_name = row["artist_name"] if isinstance(row, dict) else row[3]

        pair_key = (source_event_id, candidate_event_id)
        result.setdefault(pair_key, []).append(
            {
                "id": artist_id,
                "name": artist_name,
            }
        )

    return result

# Build semantic similar-artists API payload.
def build_artist_semantic_response(
    connection: Connection,
    *,
    artist_id: int,
    limit: int,
    debug: bool = False,
) -> SemanticArtistResponse:
    """Build API response for similar artists with semantic score breakdown."""
    min_semantic_score = artist_recommendation_min_semantic_score_from_env()
    source, scored = build_artist_semantic_candidates(
        connection,
        artist_id=artist_id,
        debug=debug,
    )
    scored = [item for item in scored if item["score"] >= min_semantic_score]
    similar = [
        SemanticArtistItem(
            id=item["entity_id"],
            name=item["name"],
            score=item["score"],
            embeddingScore=item["embedding_score"],
            styleScore=item["style_score"],
            tagScore=item["tag_score"],
            scoreBreakdown=item["score_breakdown"],
            sharedStyles=item["shared_styles"],
            sharedTags=item["shared_tags"],
            debug=item["debug"],
        )
        for item in scored[:limit]
    ]

    return SemanticArtistResponse(
        entityId=artist_id,
        model=source["model"],
        dimensions=source["dimensions"],
        similar=similar,
    )

# Build the main Artist -> Promoter recommendation response.
def build_artist_promoter_recommendation_response(
    connection: Connection,
    *,
    artist_id: int,
    limit: int,
    exclude_existing: bool,
    debug: bool,
    user_id: int,
) -> PromoterRecommendationResponse:
    """Build Artist -> Promoter recommendations with all weighted internal signals."""
    scoring_config = promoter_recommendation_scoring_from_env()
    source, semantic_candidates = build_artist_semantic_candidates(
        connection,
        artist_id=artist_id,
        debug=False,
    )
    source_artist_semantic = artist_semantic_metadata(connection, [artist_id]).get(artist_id, {})
    matching_mode = promoter_recommendation_matching_mode_from_env()
    source_artist_confirmed_styles = {
        str(style).strip().casefold()
        for style in source_artist_semantic.get("style_tags", [])
        if isinstance(style, str) and style.strip()
    }
    source_artist_style_tags = [
        str(style).strip()
        for style in source_artist_semantic.get("style_tags", [])
        if isinstance(style, str) and style.strip()
    ]
    style_candidate_ids = (
        promoter_style_candidate_ids(
            connection,
            source_style_tags=source_artist_style_tags,
            limit=scoring_config.sql_candidate_limit,
        )
        if matching_mode == "semantic_v2"
        else []
    )
    source_metadata = recommendation_item_metadata(connection, "artist", [artist_id])
    source_artist = source_metadata.get(artist_id)
    if source_artist is None:
        raise HTTPException(status_code=404, detail=f"Artist {artist_id} not found")
    artist_interest_low_threshold, artist_interest_high_threshold = (
        artist_interest_segment_thresholds(connection)
    )

    semantic_candidates_filtered = [
        item
        for item in semantic_candidates
        if item["score"] >= scoring_config.semantic_artist_min_score
    ]
    semantic_artist_below_threshold_filtered = max(
        len(semantic_candidates) - len(semantic_candidates_filtered),
        0,
    )
    candidate_scores = {
        item["entity_id"]: item["score"]
        for item in semantic_candidates_filtered[:scoring_config.semantic_artist_pool_limit]
    }
    semantic_score_by_artist = {
        int(item["entity_id"]): float(item["score"])
        for item in semantic_candidates
    }
    artist_ids = list(candidate_scores.keys())
    artist_scores = [candidate_scores[artist_id] for artist_id in artist_ids]
    manual_known_artist_ids: set[int] = set()
    manual_relevant_artist_ids: set[int] = set()
    manual_relevant_by_semantic_ids: set[int] = set()
    manual_relevant_by_profile_fallback_ids: set[int] = set()
    manual_semantic_gate_filtered_count = 0
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.artist_manual_connections') IS NOT NULL AS exists")
        manual_connections_table_exists = bool(cursor.fetchone()["exists"])
        if manual_connections_table_exists:
            cursor.execute(
                """
                SELECT connected_artist_id
                FROM artist_manual_connections
                WHERE source_artist_id = %(source_artist_id)s
                """,
                {"source_artist_id": artist_id},
            )
            manual_known_artist_ids = {
                int(row["connected_artist_id"])
                for row in cursor.fetchall()
                if row["connected_artist_id"] is not None
            }
            manual_relevant_by_semantic_ids = {
                connected_artist_id
                for connected_artist_id in manual_known_artist_ids
                if semantic_score_by_artist.get(connected_artist_id, 0.0)
                >= scoring_config.manual_warm_min_artist_semantic_score
            }
            manual_artist_metadata = artist_semantic_metadata(
                connection,
                sorted(manual_known_artist_ids),
            )
            manual_relevant_by_profile_fallback_ids = {
                connected_artist_id
                for connected_artist_id in manual_known_artist_ids
                if not manual_artist_metadata.get(connected_artist_id, {}).get("style_tags")
                and not manual_artist_metadata.get(connected_artist_id, {}).get("tags")
            }
            manual_relevant_artist_ids = (
                manual_relevant_by_semantic_ids | manual_relevant_by_profile_fallback_ids
            )
            manual_semantic_gate_filtered_count = max(
                len(manual_known_artist_ids) - len(manual_relevant_artist_ids),
                0,
            )
            manual_known_artists_cte = """
            manual_known_artists AS (
                SELECT
                    amc.connected_artist_id AS co_artist_id,
                    NULL::bigint AS shared_event_id
                FROM artist_manual_connections amc
                WHERE amc.source_artist_id = %(source_artist_id)s
                  AND amc.connected_artist_id = ANY(%(manual_relevant_artist_ids)s::bigint[])
            ),
            """
        else:
            manual_known_artists_cte = """
            manual_known_artists AS (
                SELECT
                    NULL::bigint AS co_artist_id,
                    NULL::bigint AS shared_event_id
                WHERE FALSE
            ),
            """
            logger.warning(
                "artist_manual_connections table is missing; fallback to recommendations "
                "without manual-known-artist links. Run migrations to enable this signal."
            )

        style_promoters_cte = """
            style_promoters AS (
                SELECT DISTINCT promoter_id
                FROM unnest(%(style_promoter_ids)s::bigint[]) AS style_promoter_ids(promoter_id)
            ),
            """
        style_promoters_union = """
                UNION
                SELECT promoter_id FROM style_promoters
        """ if matching_mode == "semantic_v2" else ""

        cursor.execute(
            f"""
            WITH semantic_candidates AS (
                SELECT *
                FROM unnest(%(artist_ids)s::bigint[], %(artist_scores)s::double precision[])
                    AS candidate(artist_id, semantic_score)
            ),
            source_events AS (
                SELECT DISTINCT event_id
                FROM event_artists
                WHERE artist_id = %(source_artist_id)s
            ),
            {manual_known_artists_cte}
            {style_promoters_cte if matching_mode == "semantic_v2" else ""}
            co_played_artists AS (
                SELECT DISTINCT
                    ea_shared.artist_id AS co_artist_id,
                    se.event_id AS shared_event_id
                FROM source_events se
                JOIN event_artists ea_shared
                    ON ea_shared.event_id = se.event_id
                WHERE ea_shared.artist_id <> %(source_artist_id)s
            ),
            semantic_promoters AS (
                SELECT
                    ep.promoter_id,
                    count(DISTINCT sc.artist_id)::int AS matched_artist_count,
                    array_agg(DISTINCT a.name) AS matched_artist_names,
                    count(DISTINCT e.id)::int AS event_count,
                    array_agg(DISTINCT e.title) AS related_event_titles,
                    max(sc.semantic_score)::double precision AS semantic_score,
                    max(e.event_date)::date AS latest_event_date
                FROM semantic_candidates sc
                JOIN artists a
                    ON a.id = sc.artist_id
                JOIN event_artists ea
                    ON ea.artist_id = sc.artist_id
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                GROUP BY ep.promoter_id
            ),
            direct_promoters AS (
                SELECT
                    ep.promoter_id,
                    count(DISTINCT e.id)::int AS direct_connection_count,
                    array_agg(DISTINCT e.title) AS direct_event_titles,
                    max(e.event_date)::date AS latest_direct_event_date
                FROM event_artists ea
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                WHERE ea.artist_id = %(source_artist_id)s
                GROUP BY ep.promoter_id
            ),
            warm_promoters AS (
                SELECT
                    ep.promoter_id,
                    count(DISTINCT cpa.co_artist_id)::int AS warm_connection_count,
                    jsonb_agg(
                        DISTINCT jsonb_build_object(
                            'id', cpa.co_artist_id,
                            'name', co_artist.name
                        )
                    ) AS warm_connection_artists,
                    count(DISTINCT e.id)::int AS warm_event_count,
                    array_agg(DISTINCT e.title) AS warm_event_titles,
                    max(e.event_date)::date AS latest_warm_event_date
                FROM co_played_artists cpa
                JOIN event_artists ea
                    ON ea.artist_id = cpa.co_artist_id
                JOIN artists co_artist
                    ON co_artist.id = cpa.co_artist_id
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                WHERE cpa.shared_event_id IS NULL OR e.id <> cpa.shared_event_id
                GROUP BY ep.promoter_id
            ),
            manual_warm_promoters AS (
                SELECT
                    ep.promoter_id,
                    count(DISTINCT mka.co_artist_id)::int AS manual_warm_connection_count,
                    jsonb_agg(
                        DISTINCT jsonb_build_object(
                            'id', mka.co_artist_id,
                            'name', co_artist.name
                        )
                    ) AS manual_warm_connection_artists
                FROM manual_known_artists mka
                JOIN event_artists ea
                    ON ea.artist_id = mka.co_artist_id
                JOIN artists co_artist
                    ON co_artist.id = mka.co_artist_id
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                GROUP BY ep.promoter_id
            ),
            candidate_promoters AS (
                SELECT promoter_id FROM semantic_promoters
                UNION
                SELECT promoter_id FROM direct_promoters
                UNION
                SELECT promoter_id FROM warm_promoters
                UNION
                SELECT promoter_id FROM manual_warm_promoters
                {style_promoters_union}
            ),
            promoter_interest AS (
                SELECT
                    cp.promoter_id,
                    COALESCE(sum(GREATEST(e.interested_count, 0)), 0)::bigint AS promoter_interested_sum
                FROM candidate_promoters cp
                JOIN event_promoters ep
                    ON ep.promoter_id = cp.promoter_id
                JOIN events e
                    ON e.id = ep.event_id
                GROUP BY cp.promoter_id
            )
            SELECT
                p.id,
                p.name,
                COALESCE(sp.matched_artist_count, 0)::int AS matched_artist_count,
                COALESCE(sp.matched_artist_names, ARRAY[]::text[]) AS matched_artist_names,
                GREATEST(
                    COALESCE(sp.event_count, 0),
                    COALESCE(dp.direct_connection_count, 0),
                    COALESCE(wp.warm_event_count, 0)
                )::int AS event_count,
                ARRAY(
                    SELECT DISTINCT title
                    FROM unnest(
                        COALESCE(sp.related_event_titles, ARRAY[]::text[])
                        || COALESCE(dp.direct_event_titles, ARRAY[]::text[])
                        || COALESCE(wp.warm_event_titles, ARRAY[]::text[])
                    ) AS title
                    WHERE title IS NOT NULL
                    ORDER BY title
                ) AS related_event_titles,
                COALESCE(sp.semantic_score, 0)::double precision AS semantic_score,
                COALESCE(
                    GREATEST(
                        sp.latest_event_date,
                        dp.latest_direct_event_date,
                        wp.latest_warm_event_date
                    ),
                    sp.latest_event_date,
                    dp.latest_direct_event_date,
                    wp.latest_warm_event_date
                )::date AS latest_event_date,
                COALESCE(dp.direct_connection_count, 0)::int AS direct_connection_count,
                COALESCE(wp.warm_connection_count, 0)::int AS warm_connection_count,
                COALESCE(wp.warm_connection_artists, '[]'::jsonb) AS warm_connection_artists,
                COALESCE(mwp.manual_warm_connection_count, 0)::int AS manual_warm_connection_count,
                COALESCE(mwp.manual_warm_connection_artists, '[]'::jsonb) AS manual_warm_connection_artists,
                COALESCE(pi.promoter_interested_sum, 0)::bigint AS promoter_interested_sum
            FROM candidate_promoters cp
            JOIN promoters p
                ON p.id = cp.promoter_id
            LEFT JOIN semantic_promoters sp
                ON sp.promoter_id = p.id
            LEFT JOIN direct_promoters dp
                ON dp.promoter_id = p.id
            LEFT JOIN warm_promoters wp
                ON wp.promoter_id = p.id
            LEFT JOIN manual_warm_promoters mwp
                ON mwp.promoter_id = p.id
            LEFT JOIN promoter_interest pi
                ON pi.promoter_id = p.id
            ORDER BY semantic_score DESC, direct_connection_count DESC, warm_connection_count DESC, event_count DESC, p.id ASC
            LIMIT %(sql_candidate_limit)s
            """,
            {
                "artist_ids": artist_ids,
                "artist_scores": artist_scores,
                "source_artist_id": artist_id,
                "manual_relevant_artist_ids": sorted(manual_relevant_artist_ids),
                "style_promoter_ids": style_candidate_ids,
                "sql_candidate_limit": scoring_config.sql_candidate_limit,
            },
        )
        rows = cursor.fetchall()

    event_similarity_event_titles: list[str] = []
    event_similarity_below_threshold_filtered = 0
    event_similarity_embedding_gate_filtered = 0
    event_similarity_per_promoter_limit_cutoff = 0
    event_similarity_stats_by_promoter: dict[int, dict[str, object]] = {}
    additional_promoter_ids: list[int] = []
    style_shared_genres_by_promoter: dict[int, list[str]] = {}
    style_shared_genre_sources_by_promoter: dict[int, dict[str, list[dict[str, object]]]] = {}

    if matching_mode != "semantic_v2":
        similar_event_rows, _, similar_event_debug_counts = artist_similar_events_scored_rows(
            connection,
            source_artist_id=artist_id,
            limit=max(
                limit * scoring_config.event_similarity_overfetch_multiplier,
                scoring_config.event_similarity_overfetch_min,
            ),
            exclude_same_promoter=True,
            scoring_config=scoring_config,
            collect_debug=debug,
        )
        event_similarity_below_threshold_filtered = 0
        event_similarity_embedding_gate_filtered = int(
            similar_event_debug_counts.get("embeddingGateFiltered", 0)
        )
        event_similarity_per_promoter_limit_cutoff = 0
        event_similarity_rows_by_promoter: dict[int, list[dict]] = {}
        for similar_row in similar_event_rows:
            promoter_id = similar_row.get("promoter_id")
            if promoter_id is None:
                continue
            if float(similar_row["total_similarity_score"]) < scoring_config.event_similarity_min_total_score:
                event_similarity_below_threshold_filtered += 1
                continue
            event_similarity_rows_by_promoter.setdefault(int(promoter_id), []).append(similar_row)

        filtered_similar_event_rows: list[dict] = []
        for promoter_id, promoter_rows in event_similarity_rows_by_promoter.items():
            ranked_rows = sorted(
                promoter_rows,
                key=lambda item: (-item["total_similarity_score"], item["candidate_event_id"]),
            )
            kept_rows = ranked_rows[: scoring_config.event_similarity_per_promoter_limit]
            event_similarity_per_promoter_limit_cutoff += max(len(ranked_rows) - len(kept_rows), 0)
            filtered_similar_event_rows.extend(kept_rows)

        for similar_row in filtered_similar_event_rows:
            promoter_id = similar_row.get("promoter_id")
            if promoter_id is None:
                continue
            stats = event_similarity_stats_by_promoter.setdefault(
                int(promoter_id),
                {
                    "count": 0,
                    "symbolic_sum": 0.0,
                    "embedding_sum": 0.0,
                    "latest_event_date": None,
                    "rows": [],
                },
            )
            stats["count"] = int(stats["count"]) + 1
            stats["symbolic_sum"] = float(stats["symbolic_sum"]) + float(similar_row["symbolic_score_final"])
            stats["embedding_sum"] = float(stats["embedding_sum"]) + float(similar_row["embedding_score"])
            candidate_event_date = similar_row.get("candidate_event_date")
            latest_event_date = stats["latest_event_date"]
            if candidate_event_date is not None and (
                latest_event_date is None or candidate_event_date > latest_event_date
            ):
                stats["latest_event_date"] = candidate_event_date
            stats["rows"].append(similar_row)

        existing_promoter_ids = {int(row["id"]) for row in rows}
        additional_promoter_ids = sorted(
            promoter_id
            for promoter_id in event_similarity_stats_by_promoter
            if promoter_id not in existing_promoter_ids
        )
        if additional_promoter_ids:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        p.id,
                        p.name,
                        COALESCE(sum(GREATEST(e.interested_count, 0)), 0)::bigint AS promoter_interested_sum
                    FROM promoters p
                    LEFT JOIN event_promoters ep
                        ON ep.promoter_id = p.id
                    LEFT JOIN events e
                        ON e.id = ep.event_id
                    WHERE p.id = ANY(%s)
                    GROUP BY p.id, p.name
                    """,
                    (additional_promoter_ids,),
                )
                for promoter in cursor.fetchall():
                    rows.append(
                        {
                            "id": promoter["id"],
                            "name": promoter["name"],
                            "matched_artist_count": 0,
                            "matched_artist_names": [],
                            "event_count": 0,
                            "related_event_titles": [],
                            "semantic_score": 0.0,
                            "latest_event_date": None,
                            "direct_connection_count": 0,
                            "warm_connection_count": 0,
                            "warm_connection_artists": [],
                            "manual_warm_connection_count": 0,
                            "manual_warm_connection_artists": [],
                            "promoter_interested_sum": int(promoter["promoter_interested_sum"] or 0),
                        }
                    )
    else:
        similar_event_debug_counts = {
            "embeddingGateFiltered": 0,
            "sourceEventsTotal": 0,
            "sourceEventsAfterRelevanceGate": 0,
            "sourceEventsRelevanceFiltered": 0,
            "sourceEventsMissingEmbedding": 0,
            "samePromoterFiltered": 0,
            "similarityLimitCutoff": 0,
        }
        promoter_style_profiles = load_promoter_content_profiles(
            connection,
            [int(row["id"]) for row in rows],
        )
        promoter_style_sources = load_promoter_style_sources(
            connection,
            [int(row["id"]) for row in rows],
        )
        for row in rows:
            promoter_id = int(row["id"])
            profile = promoter_style_profiles.get(promoter_id)
            candidate_genres = sorted(profile.genre_tags) if profile is not None else []
            shared_genres = shared_tag_values(source_artist_style_tags, candidate_genres)
            if shared_genres:
                style_shared_genres_by_promoter[promoter_id] = shared_genres
            sources_by_genre = promoter_style_sources.get(promoter_id, {})
            genre_sources = {
                genre: sources_by_genre.get(genre.casefold(), [])
                for genre in shared_genres
                if sources_by_genre.get(genre.casefold(), [])
            }
            if genre_sources:
                style_shared_genre_sources_by_promoter[promoter_id] = genre_sources

    promoter_interest_low_threshold, promoter_interest_high_threshold = interested_tertile_thresholds(
        [int(row.get("promoter_interested_sum", 0) or 0) for row in rows]
    )

    source_scale_stats = source_artist_scale_stats(connection, artist_id=artist_id)
    source_artist_event_count = max(int(source_scale_stats["event_count"]), 1)
    source_artist_avg_interested = source_scale_stats.get("avg_interested")
    source_artist_size_segment = interest_segment_label(
        source_artist_avg_interested,
        low_threshold=artist_interest_low_threshold,
        high_threshold=artist_interest_high_threshold,
    )
    source_artist_scale = float(source_artist_event_count)

    recommendations = []
    exclude_existing_filtered_count = 0
    for row in rows:
        if exclude_existing and row["direct_connection_count"] > 0:
            exclude_existing_filtered_count += 1
            continue
        if matching_mode == "semantic_v2":
            source_styles = source_artist_style_tags
            shared_extracted_genres = style_shared_genres_by_promoter.get(row["id"], [])
            shared_extracted_genre_sources = style_shared_genre_sources_by_promoter.get(row["id"], {})
            shared_themes = []
            shared_moods = []
            event_similarity_count = 0
            event_similarity_average_symbolic_score = style_overlap_score(
                source_styles,
                shared_extracted_genres,
            )
            event_similarity_embedding_score = 0.0
            event_similarity_symbolic_score = event_similarity_average_symbolic_score
            event_similarity_score = event_similarity_symbolic_score
            event_similarity_event_titles = []
            event_similarity_stats = None
        else:
            event_similarity_stats = event_similarity_stats_by_promoter.get(row["id"])
            event_similarity_count = int(event_similarity_stats["count"]) if event_similarity_stats else 0
            event_similarity_average_symbolic_score = (
                float(event_similarity_stats["symbolic_sum"]) / event_similarity_count
                if event_similarity_count > 0 and event_similarity_stats is not None
                else 0.0
            )
            event_similarity_embedding_score = (
                float(event_similarity_stats["embedding_sum"]) / event_similarity_count
                if event_similarity_count > 0 and event_similarity_stats is not None
                else 0.0
            )
            event_similarity_symbolic_score = (
                min(
                    event_similarity_count / scoring_config.event_similarity_count_cap,
                    1.0,
                )
                * event_similarity_average_symbolic_score
            )
            event_similarity_score = (
                scoring_config.event_similarity_symbolic_weight * event_similarity_symbolic_score
                + scoring_config.event_similarity_embedding_weight * event_similarity_embedding_score
            )
            shared_extracted_genres = []
            shared_extracted_genre_sources = {}
            shared_themes = []
            shared_moods = []
            event_similarity_event_titles = []
        direct_connection_score = min(
            row["direct_connection_count"] / scoring_config.direct_connection_cap,
            1.0,
        )
        effective_event_count = max(
            min(int(row["event_count"]), scoring_config.strength_event_cap),
            event_similarity_count,
        )
        effective_latest_event_date = row["latest_event_date"]
        if event_similarity_stats is not None and event_similarity_stats["latest_event_date"] is not None:
            similarity_latest_event_date = event_similarity_stats["latest_event_date"]
            if effective_latest_event_date is None or similarity_latest_event_date > effective_latest_event_date:
                effective_latest_event_date = similarity_latest_event_date
        strength_score = min(
            (
                row["matched_artist_count"] / scoring_config.strength_matched_artist_cap
                * scoring_config.strength_matched_artist_weight
            )
            + (
                effective_event_count / scoring_config.strength_event_cap
                * scoring_config.strength_event_weight
            ),
            1.0,
        )
        activity_score = min(effective_event_count / scoring_config.activity_event_cap, 1.0)
        recency_score = date_recency_score(effective_latest_event_date)
        promoter_scale = float(max(effective_event_count, 1))
        promoter_interested_sum = int(row.get("promoter_interested_sum", 0) or 0)
        promoter_size_segment = interest_segment_label(
            promoter_interested_sum,
            low_threshold=promoter_interest_low_threshold,
            high_threshold=promoter_interest_high_threshold,
        )
        scale_bucket_multiplier = scale_bucket_match_multiplier(
            source_artist_event_count,
            effective_event_count,
        )
        scale_fit = scale_fit_score(
            artist_scale=source_artist_scale,
            promoter_scale=promoter_scale,
            alpha=scoring_config.scale_fit_alpha,
            tau=scoring_config.scale_fit_tau,
        ) * scale_bucket_multiplier
        warm_connection_artists_raw = row.get("warm_connection_artists")
        warm_connection_artists: list[dict[str, object]] = []
        if isinstance(warm_connection_artists_raw, list):
            for item in warm_connection_artists_raw:
                if not isinstance(item, dict):
                    continue
                artist_id_value = item.get("id")
                artist_name_value = item.get("name")
                if artist_id_value is None or artist_name_value is None:
                    continue
                warm_connection_artists.append(
                    {
                        "id": int(artist_id_value),
                        "name": str(artist_name_value),
                    }
                )
        warm_connection_artists.sort(key=lambda item: item["id"])
        manual_connection_artists_raw = row.get("manual_warm_connection_artists")
        manual_connection_artists: list[dict[str, object]] = []
        if isinstance(manual_connection_artists_raw, list):
            for item in manual_connection_artists_raw:
                if not isinstance(item, dict):
                    continue
                artist_id_value = item.get("id")
                artist_name_value = item.get("name")
                if artist_id_value is None or artist_name_value is None:
                    continue
                manual_connection_artists.append(
                    {
                        "id": int(artist_id_value),
                        "name": str(artist_name_value),
                    }
                )
        manual_connection_artists.sort(key=lambda item: item["id"])
        manual_warm_connection_count_raw = int(row.get("manual_warm_connection_count", 0) or 0)
        manual_overlap_with_warm_count = sum(
            1
            for item in warm_connection_artists
            if int(item["id"]) in manual_known_artist_ids
        )
        manual_warm_connection_count = max(
            manual_warm_connection_count_raw,
            manual_overlap_with_warm_count,
        )
        manual_relevant_overlap_with_warm_count = sum(
            1
            for item in warm_connection_artists
            if int(item["id"]) in manual_relevant_artist_ids
        )
        manual_relevant_warm_connection_count = max(
            manual_warm_connection_count_raw,
            manual_relevant_overlap_with_warm_count,
        )
        matched_artist_names_raw = row.get("matched_artist_names")
        matched_artist_names = (
            sorted({name.strip() for name in matched_artist_names_raw if isinstance(name, str) and name.strip()})
            if isinstance(matched_artist_names_raw, list)
            else []
        )
        if matching_mode == "semantic_v2":
            event_similarity_event_titles = []
        else:
            event_similarity_event_titles = []
            if event_similarity_stats is not None:
                seen_event_titles: set[str] = set()
                for item in sorted(
                    event_similarity_stats["rows"],
                    key=lambda candidate: (-candidate["total_similarity_score"], candidate["candidate_event_id"]),
                ):
                    title = item.get("candidate_event_title")
                    if not isinstance(title, str):
                        continue
                    normalized_title = title.strip()
                    if not normalized_title or normalized_title in seen_event_titles:
                        continue
                    seen_event_titles.add(normalized_title)
                    event_similarity_event_titles.append(normalized_title)
        if matching_mode == "semantic_v2":
            shared_extracted_genres = style_shared_genres_by_promoter.get(row["id"], [])
            shared_extracted_genre_sources = style_shared_genre_sources_by_promoter.get(row["id"], {})
            shared_themes = []
            shared_moods = []
        else:
            shared_extracted_genres = []
            shared_extracted_genre_sources = {}
            shared_themes = []
            shared_moods = []
            if event_similarity_stats is not None:
                shared_tag_rows = sorted(
                    event_similarity_stats["rows"],
                    key=lambda item: (-item["total_similarity_score"], item["candidate_event_id"]),
                )[:5]
                for item in shared_tag_rows:
                    row_shared_genres = [
                        str(tag).strip()
                        for tag in item.get("shared_extracted_genres", [])
                        if isinstance(tag, str) and tag.strip()
                    ]
                    if source_artist_confirmed_styles:
                        row_shared_genres = [
                            tag for tag in row_shared_genres if tag.casefold() in source_artist_confirmed_styles
                        ]
                    for tag in row_shared_genres:
                        normalized_tag = str(tag).strip()
                        if normalized_tag and normalized_tag not in shared_extracted_genres:
                            shared_extracted_genres.append(normalized_tag)
                    for tag in item.get("shared_themes", []):
                        normalized_tag = str(tag).strip()
                        if normalized_tag and normalized_tag not in shared_themes:
                            shared_themes.append(normalized_tag)
                    for tag in item.get("shared_moods", []):
                        normalized_tag = str(tag).strip()
                        if normalized_tag and normalized_tag not in shared_moods:
                            shared_moods.append(normalized_tag)
        row_with_similarity = {
            **row,
            "event_similarity_count": event_similarity_count,
            "event_count": effective_event_count,
            "latest_event_date": effective_latest_event_date,
            "warm_connection_artists": warm_connection_artists,
            "manual_warm_connection_count": manual_warm_connection_count,
            "manual_warm_connection_artists": manual_connection_artists,
            "matched_artist_names": matched_artist_names,
            "event_similarity_event_titles": event_similarity_event_titles,
            "shared_extracted_genres": shared_extracted_genres,
            "shared_extracted_genre_sources": shared_extracted_genre_sources,
            "shared_themes": shared_themes,
            "shared_moods": shared_moods,
        }
        co_played_connection_score = min(
            row["warm_connection_count"] / scoring_config.warm_connection_cap,
            1.0,
        )
        manual_connection_score = min(
            manual_relevant_warm_connection_count / scoring_config.manual_warm_connection_cap,
            1.0,
        )
        direct_weight = 0.0 if exclude_existing else scoring_config.direct_connection_weight
        co_played_contribution = (
            scoring_config.co_played_connection_weight * co_played_connection_score
        )
        manual_connection_contribution = (
            scoring_config.manual_connection_weight * manual_connection_score
        )
        semantic_contribution = scoring_config.semantic_weight * row["semantic_score"]
        strength_contribution = scoring_config.strength_weight * strength_score
        direct_contribution = direct_weight * direct_connection_score
        event_similarity_contribution = (
            scoring_config.event_similarity_weight * event_similarity_score
        )
        scale_fit_contribution = scoring_config.scale_fit_weight * scale_fit
        activity_contribution = scoring_config.activity_weight * activity_score
        recency_contribution = scoring_config.recency_weight * recency_score
        score_breakdown = {
            "semantic": semantic_contribution,
            "strength": strength_contribution,
            "directConnection": direct_contribution,
            "coPlayedConnection": co_played_contribution,
            "manualConnection": manual_connection_contribution,
            "eventSimilarity": event_similarity_contribution,
            "scaleFit": scale_fit_contribution,
            "activity": activity_contribution,
            "recency": recency_contribution,
        }
        total_score = (
            semantic_contribution
            + strength_contribution
            + direct_contribution
            + co_played_contribution
            + manual_connection_contribution
            + event_similarity_contribution
            + scale_fit_contribution
            + activity_contribution
            + recency_contribution
        )
        has_warm_path = row["warm_connection_count"] > 0 or manual_warm_connection_count > 0
        adjusted_score = promoter_recommendation_adjusted_score(
            total_score,
            has_warm_path=has_warm_path,
        )
        recommendations.append(
            PromoterRecommendationItem(
                id=row["id"],
                name=row["name"],
                score=adjusted_score,
                semanticScore=row["semantic_score"],
                strengthScore=strength_score,
                activityScore=activity_score,
                recencyScore=recency_score,
                scoreBreakdown=score_breakdown,
                reasons=promoter_recommendation_reasons(row_with_similarity),
                matchedArtistCount=row["matched_artist_count"],
                eventCount=effective_event_count,
                latestEventDate=effective_latest_event_date,
                status=promoter_recommendation_status(row_with_similarity, scoring_config),
                warmConnectionCount=row["warm_connection_count"],
                warmConnectionArtists=warm_connection_artists,
                coPlayedConnectionCount=row["warm_connection_count"],
                coPlayedConnectionArtists=warm_connection_artists,
                manualConnectionCount=manual_warm_connection_count,
                manualConnectionArtists=manual_connection_artists,
                promoterInterestedSum=promoter_interested_sum,
                promoterSizeSegment=promoter_size_segment,
                directConnectionCount=row["direct_connection_count"],
                evidence=promoter_recommendation_item_evidence(row_with_similarity),
                reasonDetails={
                    "similarPromoterEventTitles": event_similarity_event_titles,
                    "sharedExtractedGenres": shared_extracted_genres,
                    "sharedExtractedGenreSources": shared_extracted_genre_sources,
                    "sharedThemes": shared_themes,
                    "sharedMoods": shared_moods,
                    "similarArtistNames": matched_artist_names,
                    "coPlayedArtistNames": [str(item.get("name", "")) for item in warm_connection_artists if item.get("name")],
                    "manualArtistNames": [str(item.get("name", "")) for item in manual_connection_artists if item.get("name")],
                },
                debug={
                    "rawSignals": {
                        "semanticScore": row["semantic_score"],
                        "matchedArtistCount": row["matched_artist_count"],
                        "eventCount": effective_event_count,
                        "eventCountRaw": int(row["event_count"]),
                        "directConnectionCount": row["direct_connection_count"],
                        "warmConnectionCount": row["warm_connection_count"],
                        "coPlayedConnectionCount": row["warm_connection_count"],
                        "manualWarmConnectionCount": manual_warm_connection_count,
                        "manualWarmConnectionCountRaw": manual_warm_connection_count_raw,
                        "manualWarmOverlapWithWarmCount": manual_overlap_with_warm_count,
                        "manualRelevantWarmConnectionCount": manual_relevant_warm_connection_count,
                        "manualRelevantOverlapWithWarmCount": manual_relevant_overlap_with_warm_count,
                        "manualKnownArtistCount": len(manual_known_artist_ids),
                        "manualRelevantArtistCount": len(manual_relevant_artist_ids),
                        "manualRelevantBySemanticCount": len(manual_relevant_by_semantic_ids),
                        "manualRelevantByProfileFallbackCount": len(manual_relevant_by_profile_fallback_ids),
                        "manualSemanticGateFilteredCount": manual_semantic_gate_filtered_count,
                        "manualWarmMinArtistSemanticScore": scoring_config.manual_warm_min_artist_semantic_score,
                        "coPlayedConnectionWeight": scoring_config.co_played_connection_weight,
                        "manualConnectionWeight": scoring_config.manual_connection_weight,
                        "manualConnectionArtists": manual_connection_artists,
                        "eventSimilarityCount": event_similarity_count,
                        "eventSimilaritySymbolicScore": event_similarity_symbolic_score,
                        "eventSimilarityEmbeddingScore": event_similarity_embedding_score,
                        "eventSimilarityEventTitles": event_similarity_event_titles,
                        "sharedExtractedGenres": shared_extracted_genres,
                        "sharedExtractedGenreSources": shared_extracted_genre_sources,
                        "sharedThemes": shared_themes,
                        "sharedMoods": shared_moods,
                        "matchedArtistNames": matched_artist_names,
                        "artistScale": source_artist_scale,
                        "promoterScale": promoter_scale,
                        "promoterInterestedSum": promoter_interested_sum,
                        "promoterSizeSegment": promoter_size_segment,
                        "artistScaleEventCount": source_artist_event_count,
                        "promoterScaleEventCount": effective_event_count,
                        "scaleBucketMultiplier": scale_bucket_multiplier,
                        "scaleFit": scale_fit,
                        "warmConnectionArtists": warm_connection_artists,
                        "coPlayedConnectionArtists": warm_connection_artists,
                    },
                    "normalizedScores": {
                        "strength": strength_score,
                        "directConnection": direct_connection_score,
                        "coPlayedConnection": co_played_connection_score,
                        "manualConnection": manual_connection_score,
                        "eventSimilarity": event_similarity_score,
                        "scaleFit": scale_fit,
                        "activity": activity_score,
                        "recency": recency_score,
                    },
                    "weightedScores": {
                        **score_breakdown,
                        "total": adjusted_score,
                    },
                }
                if debug
                else None,
            )
        )

    feedback_by_promoter_id = load_promoter_feedback(
        connection,
        user_id=user_id,
        artist_id=artist_id,
    )
    feedback_config = promoter_feedback_config_from_env()
    content_similarity_by_promoter_id = promoter_content_similarities(
        connection,
        candidate_promoter_ids=[recommendation.id for recommendation in recommendations],
        positive_promoter_ids=[
            promoter_id
            for promoter_id, feedback in feedback_by_promoter_id.items()
            if feedback == "positive"
        ],
        config=feedback_config,
    )
    recommendations = apply_promoter_feedback_reranking(
        recommendations,
        feedback_by_promoter_id=feedback_by_promoter_id,
        content_similarity_by_promoter_id=content_similarity_by_promoter_id,
        config=feedback_config,
    )
    sorted_recommendations = sorted(
        recommendations,
        key=lambda recommendation: (-recommendation.score, recommendation.id),
    )
    segment_order = promoter_segment_sort_order(source_artist_size_segment)
    size_sort_order = {segment: index for index, segment in enumerate(segment_order)}
    segment_quota_ratios_by_source = promoter_segment_quota_ratios_from_env()
    segment_quota_ratios = segment_quota_ratios_by_source[source_artist_size_segment]
    segment_warm_share = promoter_segment_warm_share_from_env()
    applied_segment_quotas = segment_quota_counts(
        limit=limit,
        segment_order=segment_order,
        segment_ratios=segment_quota_ratios,
    )
    warm_recommendations_all = [
        recommendation
        for recommendation in sorted_recommendations
        if recommendation.warmConnectionCount > 0 or recommendation.manualConnectionCount > 0
    ]
    discovery_recommendations_all = [
        recommendation
        for recommendation in sorted_recommendations
        if recommendation.warmConnectionCount == 0 and recommendation.manualConnectionCount == 0
    ]
    segmented_ranked_pool: dict[str, list[PromoterRecommendationItem]] = {}
    segment_quota_allocations: dict[str, dict[str, int]] = {}
    for segment in segment_order:
        segment_candidates = [
            recommendation
            for recommendation in sorted_recommendations
            if recommendation.promoterSizeSegment == segment
        ]
        segment_warm = [
            recommendation
            for recommendation in segment_candidates
            if recommendation.warmConnectionCount > 0 or recommendation.manualConnectionCount > 0
        ]
        segment_discovery = [
            recommendation
            for recommendation in segment_candidates
            if recommendation.warmConnectionCount == 0 and recommendation.manualConnectionCount == 0
        ]
        quota = applied_segment_quotas.get(segment, 0)
        warm_quota = min(len(segment_warm), int(math.floor(float(quota) * segment_warm_share)))
        discovery_quota = min(len(segment_discovery), max(quota - warm_quota, 0))
        selected_ids: set[int] = set()
        selected_segment: list[PromoterRecommendationItem] = []
        for recommendation in [*segment_warm[:warm_quota], *segment_discovery[:discovery_quota]]:
            selected_segment.append(recommendation)
            selected_ids.add(recommendation.id)
        remaining_segment_slots = max(quota - len(selected_segment), 0)
        if remaining_segment_slots > 0:
            backfill_segment = [
                recommendation
                for recommendation in segment_candidates
                if recommendation.id not in selected_ids
            ][:remaining_segment_slots]
            selected_segment.extend(backfill_segment)
        segment_quota_allocations[segment] = {
            "quota": quota,
            "warmQuotaTarget": int(math.floor(float(quota) * segment_warm_share)),
            "warmSelected": sum(
                1
                for recommendation in selected_segment
                if recommendation.warmConnectionCount > 0 or recommendation.manualConnectionCount > 0
            ),
            "discoverySelected": sum(
                1
                for recommendation in selected_segment
                if recommendation.warmConnectionCount == 0 and recommendation.manualConnectionCount == 0
            ),
        }
        segmented_ranked_pool[segment] = selected_segment

    recommendations = []
    for segment in segment_order:
        recommendations.extend(segmented_ranked_pool[segment])

    remaining_slots = max(limit - len(recommendations), 0)
    if remaining_slots > 0:
        backfill_pool: list[PromoterRecommendationItem] = []
        for segment in segment_order:
            segment_candidates = [
                recommendation
                for recommendation in sorted_recommendations
                if recommendation.promoterSizeSegment == segment
            ]
            selected_ids = {recommendation.id for recommendation in segmented_ranked_pool[segment]}
            backfill_pool.extend(
                recommendation
                for recommendation in segment_candidates
                if recommendation.id not in selected_ids
            )
        recommendations.extend(backfill_pool[:remaining_slots])

    recommendations = sorted(
        recommendations[:limit],
        key=lambda recommendation: (-recommendation.score, recommendation.id),
    )
    warm_recommendations = [
        recommendation
        for recommendation in recommendations
        if recommendation.warmConnectionCount > 0 or recommendation.manualConnectionCount > 0
    ]
    discovery_recommendations = [
        recommendation
        for recommendation in recommendations
        if recommendation.warmConnectionCount == 0 and recommendation.manualConnectionCount == 0
    ]
    large_recommendations = [
        recommendation for recommendation in recommendations if recommendation.promoterSizeSegment == "large"
    ]
    medium_recommendations = [
        recommendation for recommendation in recommendations if recommendation.promoterSizeSegment == "medium"
    ]
    small_recommendations = [
        recommendation for recommendation in recommendations if recommendation.promoterSizeSegment == "small"
    ]
    recommendation_limit_cutoff = max(len(sorted_recommendations) - len(recommendations), 0)
    warm_limit_cutoff = max(len(warm_recommendations_all) - len(warm_recommendations), 0)
    discovery_limit_cutoff = max(len(discovery_recommendations_all) - len(discovery_recommendations), 0)
    if not recommendations:
        return PromoterRecommendationResponse(
            entityId=artist_id,
            model=source["model"],
            dimensions=source["dimensions"],
            recommendations=[],
            largeRecommendations=[],
            mediumRecommendations=[],
            smallRecommendations=[],
            warmRecommendations=[],
            discoveryRecommendations=[],
            graph=GraphResponse(nodes=[], links=[], graphMode="compact"),
            analyticsGraph=GraphResponse(nodes=[], links=[], graphMode="full"),
            debug={
                "candidateCounts": {
                    "sqlPromoterCandidates": len(rows),
                    "semanticArtistsUsed": len(candidate_scores),
                    "sourceEventsTotal": similar_event_debug_counts["sourceEventsTotal"],
                    "sourceEventsAfterRelevanceGate": similar_event_debug_counts[
                        "sourceEventsAfterRelevanceGate"
                    ],
                    "eventSimilarityPromotersAdded": len(additional_promoter_ids),
                    "warmCandidates": 0,
                    "coPlayedCandidates": 0,
                    "manualConnectionCandidates": 0,
                    "discoveryCandidates": 0,
                    "recommendationsBeforeLimit": 0,
                    "returnedRecommendations": 0,
                    "returnedWarmRecommendations": 0,
                    "returnedCoPlayedRecommendations": 0,
                    "returnedDiscoveryRecommendations": 0,
                    "returnedLargeRecommendations": 0,
                    "returnedMediumRecommendations": 0,
                    "returnedSmallRecommendations": 0,
                },
                "filteredOut": {
                    "excludeExisting": exclude_existing_filtered_count,
                    "semanticArtistBelowThreshold": semantic_artist_below_threshold_filtered,
                    "sourceEventRelevance": similar_event_debug_counts["sourceEventsRelevanceFiltered"],
                    "sourceEventMissingEmbedding": similar_event_debug_counts[
                        "sourceEventsMissingEmbedding"
                    ],
                    "eventSimilaritySamePromoter": similar_event_debug_counts["samePromoterFiltered"],
                    "eventSimilarityLimitCutoff": similar_event_debug_counts["similarityLimitCutoff"],
                    "eventSimilarityEmbeddingGate": event_similarity_embedding_gate_filtered,
                    "eventSimilarityBelowThreshold": event_similarity_below_threshold_filtered,
                    "eventSimilarityPerPromoterLimitCutoff": event_similarity_per_promoter_limit_cutoff,
                    "recommendationLimitCutoff": 0,
                    "warmLimitCutoff": 0,
                    "discoveryLimitCutoff": 0,
                },
                "segments": {
                    "promoterInterestedSumThresholds": {
                        "smallMax": promoter_interest_low_threshold,
                        "mediumMax": promoter_interest_high_threshold,
                    },
                    "sourceArtistAverageInterested": source_artist_avg_interested,
                    "sourceArtistSizeSegment": source_artist_size_segment,
                    "appliedPromoterSegmentSortOrder": [*size_sort_order.keys()],
                    "appliedPromoterSegmentQuotaRatios": segment_quota_ratios,
                    "appliedPromoterSegmentQuotaCounts": applied_segment_quotas,
                    "appliedPromoterSegmentWarmShare": segment_warm_share,
                    "appliedPromoterSegmentSelections": segment_quota_allocations,
                    "artistAverageInterestedThresholds": {
                        "smallMax": artist_interest_low_threshold,
                        "mediumMax": artist_interest_high_threshold,
                    },
                },
            }
            if debug
            else None,
        )

    promoter_ids = [recommendation.id for recommendation in recommendations]
    semantic_evidence = promoter_recommendation_evidence(
        connection,
        promoter_ids=promoter_ids,
        semantic_scores=candidate_scores,
    )
    direct_evidence = (
        []
        if exclude_existing
        else promoter_direct_connection_evidence(
            connection,
            source_artist_id=artist_id,
            promoter_ids=promoter_ids,
        )
    )
    warm_evidence = promoter_warm_network_evidence(
        connection,
        source_artist_id=artist_id,
        promoter_ids=promoter_ids,
    )
    promoter_manual_artist_ids: dict[int, list[int]] = {}
    for recommendation in recommendations:
        trusted_artist_ids = sorted({artist.id for artist in recommendation.manualConnectionArtists})
        if trusted_artist_ids:
            promoter_manual_artist_ids[recommendation.id] = trusted_artist_ids
    manual_evidence = promoter_manual_connection_evidence(
        connection,
        promoter_manual_artist_ids=promoter_manual_artist_ids,
    )
    event_similarity_evidence: list[dict] = []
    if matching_mode != "semantic_v2":
        event_similarity_pairs: list[tuple[int, int]] = []
        for promoter_id in promoter_ids:
            similarity_stats = event_similarity_stats_by_promoter.get(promoter_id)
            if similarity_stats is None:
                continue
            ranked_rows = sorted(
                similarity_stats["rows"],
                key=lambda item: (-item["total_similarity_score"], item["candidate_event_id"]),
            )[:5]
            for item in ranked_rows:
                source_event_id = int(item["source_event_id"])
                candidate_event_id = int(item["candidate_event_id"])
                event_similarity_pairs.append((source_event_id, candidate_event_id))
                event_similarity_evidence.append(
                    {
                        "promoter_id": promoter_id,
                        "source_event_id": source_event_id,
                        "source_event_title": item["source_event_title"],
                        "source_event_date": item["source_event_date"],
                        "promoter_event_id": candidate_event_id,
                        "promoter_event_title": item["candidate_event_title"],
                        "promoter_event_date": item["candidate_event_date"],
                        "promoter_venue_id": item["candidate_venue_id"],
                        "promoter_venue_name": item["candidate_venue_name"],
                        "path_similarity": item["symbolic_score_final"],
                    }
                )

        shared_artists_by_pair = event_similarity_shared_artists_by_pair(
            connection,
            source_artist_id=artist_id,
            event_pairs=event_similarity_pairs,
        )
        for row in event_similarity_evidence:
            pair_key = (int(row["source_event_id"]), int(row["promoter_event_id"]))
            row["shared_artists"] = shared_artists_by_pair.get(pair_key, [])

    analytics_graph = promoter_recommendation_graph(
        source_artist_id=artist_id,
        source_artist_name=source_artist["name"],
        recommendations=recommendations,
        semantic_evidence_rows=semantic_evidence,
        direct_evidence_rows=direct_evidence,
        warm_evidence_rows=warm_evidence,
        manual_evidence_rows=manual_evidence,
        event_similarity_evidence_rows=event_similarity_evidence,
        scoring_config=scoring_config,
    )
    compact_graph = project_compact_recommendation_graph(
        analytics_graph,
        recommendations=recommendations,
    )

    return PromoterRecommendationResponse(
        entityId=artist_id,
        model=source["model"],
        dimensions=source["dimensions"],
        recommendations=recommendations,
        largeRecommendations=large_recommendations,
        mediumRecommendations=medium_recommendations,
        smallRecommendations=small_recommendations,
        warmRecommendations=warm_recommendations,
        discoveryRecommendations=discovery_recommendations,
        graph=compact_graph,
        analyticsGraph=analytics_graph,
        debug={
            "candidateCounts": {
                "sqlPromoterCandidates": len(rows),
                "semanticArtistsUsed": len(candidate_scores),
                "sourceEventsTotal": similar_event_debug_counts["sourceEventsTotal"],
                "sourceEventsAfterRelevanceGate": similar_event_debug_counts[
                    "sourceEventsAfterRelevanceGate"
                ],
                "eventSimilarityPromotersAdded": len(additional_promoter_ids),
                "warmCandidates": len(warm_recommendations_all),
                "coPlayedCandidates": sum(
                    1 for recommendation in warm_recommendations_all if recommendation.warmConnectionCount > 0
                ),
                "manualConnectionCandidates": sum(
                    1 for recommendation in warm_recommendations_all if recommendation.manualConnectionCount > 0
                ),
                "discoveryCandidates": len(discovery_recommendations_all),
                "recommendationsBeforeLimit": len(recommendations) + recommendation_limit_cutoff,
                "returnedRecommendations": len(recommendations),
                "returnedWarmRecommendations": len(warm_recommendations),
                "returnedCoPlayedRecommendations": sum(
                    1 for recommendation in warm_recommendations if recommendation.warmConnectionCount > 0
                ),
                "returnedDiscoveryRecommendations": len(discovery_recommendations),
                "returnedLargeRecommendations": len(large_recommendations),
                "returnedMediumRecommendations": len(medium_recommendations),
                "returnedSmallRecommendations": len(small_recommendations),
            },
            "filteredOut": {
                "excludeExisting": exclude_existing_filtered_count,
                "semanticArtistBelowThreshold": semantic_artist_below_threshold_filtered,
                "sourceEventRelevance": similar_event_debug_counts["sourceEventsRelevanceFiltered"],
                "sourceEventMissingEmbedding": similar_event_debug_counts[
                    "sourceEventsMissingEmbedding"
                ],
                "eventSimilaritySamePromoter": similar_event_debug_counts["samePromoterFiltered"],
                "eventSimilarityLimitCutoff": similar_event_debug_counts["similarityLimitCutoff"],
                "eventSimilarityEmbeddingGate": event_similarity_embedding_gate_filtered,
                "eventSimilarityBelowThreshold": event_similarity_below_threshold_filtered,
                "eventSimilarityPerPromoterLimitCutoff": event_similarity_per_promoter_limit_cutoff,
                "recommendationLimitCutoff": recommendation_limit_cutoff,
                "warmLimitCutoff": warm_limit_cutoff,
                "discoveryLimitCutoff": discovery_limit_cutoff,
            },
            "segments": {
                "promoterInterestedSumThresholds": {
                    "smallMax": promoter_interest_low_threshold,
                    "mediumMax": promoter_interest_high_threshold,
                },
                "sourceArtistAverageInterested": source_artist_avg_interested,
                "sourceArtistSizeSegment": source_artist_size_segment,
                "appliedPromoterSegmentSortOrder": [*size_sort_order.keys()],
                "appliedPromoterSegmentQuotaRatios": segment_quota_ratios,
                "appliedPromoterSegmentQuotaCounts": applied_segment_quotas,
                "appliedPromoterSegmentWarmShare": segment_warm_share,
                "appliedPromoterSegmentSelections": segment_quota_allocations,
                "artistAverageInterestedThresholds": {
                    "smallMax": artist_interest_low_threshold,
                    "mediumMax": artist_interest_high_threshold,
                },
            },
        }
        if debug
        else None,
    )
