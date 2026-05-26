from __future__ import annotations

import logging
import math

from fastapi import HTTPException
from psycopg import Connection

from app.event_similarity import artist_similar_events_scored_rows
from app.promoter_graph import (
    date_recency_score,
    promoter_direct_connection_evidence,
    promoter_recommendation_evidence,
    promoter_recommendation_graph,
    promoter_recommendation_item_evidence,
    promoter_recommendation_reasons,
    promoter_recommendation_status,
    promoter_warm_network_evidence,
)
from app.recommendation_engine import (
    apply_artist_indirect_features,
    recommendation_feature_sets,
)
from app.recommendation_helpers import build_artist_semantic_candidates, recommendation_item_metadata
from app.recommendation_scoring import (
    DEFAULT_RECOMMENDATION_SCORING,
    final_recommendation_score,
    hybrid_graph_score,
    promoter_recommendation_scoring_from_env,
)
from app.schemas import (
    ArtistRecommendationItem,
    ArtistRecommendationResponse,
    GraphResponse,
    PromoterRecommendationItem,
    PromoterRecommendationResponse,
    SemanticArtistItem,
    SemanticArtistResponse,
)

logger = logging.getLogger(__name__)


def semantic_artist_reasons(item: dict) -> list[str]:
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


def source_artist_scale_stats(connection: Connection, *, artist_id: int) -> dict[str, int | float | None]:
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
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY e.interested_count)::double precision
                        AS median_interested
                FROM source_events se
                JOIN events e
                    ON e.id = se.event_id
                WHERE e.interested_count IS NOT NULL
            )
            SELECT ss.event_count, si.median_interested
            FROM source_scales ss
            CROSS JOIN source_interested si
            """,
            (artist_id,),
        )
        row = cursor.fetchone()
    if row is None:
        return {"event_count": 0, "median_interested": None}
    return row


def scale_fit_score(
    *,
    artist_scale: float,
    promoter_scale: float,
    alpha: float,
    tau: float,
) -> float:
    ratio = (promoter_scale + alpha) / (artist_scale + alpha)
    return math.exp(-abs(math.log(ratio)) / tau)


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


def scale_bucket_match_multiplier(source_event_count: int, promoter_event_count: int) -> float:
    distance = abs(scale_bucket(source_event_count) - scale_bucket(promoter_event_count))
    if distance == 0:
        return 1.0
    if distance == 1:
        return 0.65
    return 0.30


def build_artist_semantic_response(
    connection: Connection,
    *,
    artist_id: int,
    limit: int,
    debug: bool = False,
) -> SemanticArtistResponse:
    source, scored = build_artist_semantic_candidates(
        connection,
        artist_id=artist_id,
        debug=debug,
    )
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


def build_artist_recommendation_response(
    connection: Connection,
    *,
    artist_id: int,
    limit: int,
) -> ArtistRecommendationResponse:
    source, semantic_candidates = build_artist_semantic_candidates(
        connection,
        artist_id=artist_id,
        debug=False,
    )
    candidate_ids = [item["entity_id"] for item in semantic_candidates]
    features = recommendation_feature_sets(connection, "artist", [artist_id, *candidate_ids])
    features = apply_artist_indirect_features(
        connection,
        entity_type="artist",
        entity_id=artist_id,
        candidate_ids=candidate_ids,
        features=features,
    )
    source_features = features.get(artist_id, {})

    recommendations = []
    for item in semantic_candidates:
        candidate_features = features.get(item["entity_id"], {})
        graph_score, graph_reasons = hybrid_graph_score("artist", source_features, candidate_features)
        final_score = final_recommendation_score(
            item["score"],
            graph_score,
            DEFAULT_RECOMMENDATION_SCORING,
        )
        score_breakdown = {
            "semantic": DEFAULT_RECOMMENDATION_SCORING.semantic_weight * item["score"],
            "graph": DEFAULT_RECOMMENDATION_SCORING.graph_weight * graph_score,
        }
        reasons = [
            *semantic_artist_reasons(item),
            *graph_reasons,
        ][:5]
        recommendations.append(
            ArtistRecommendationItem(
                id=item["entity_id"],
                name=item["name"],
                score=final_score,
                semanticScore=item["score"],
                graphScore=graph_score,
                embeddingScore=item["embedding_score"],
                styleScore=item["style_score"],
                tagScore=item["tag_score"],
                scoreBreakdown=score_breakdown,
                semanticBreakdown=item["score_breakdown"],
                reasons=reasons,
                sharedStyles=item["shared_styles"],
                sharedTags=item["shared_tags"],
            )
        )

    return ArtistRecommendationResponse(
        entityId=artist_id,
        model=source["model"],
        dimensions=source["dimensions"],
        recommendations=sorted(
            recommendations,
            key=lambda recommendation: (-recommendation.score, recommendation.id),
        )[:limit],
    )


def build_artist_promoter_recommendation_response(
    connection: Connection,
    *,
    artist_id: int,
    limit: int,
    exclude_existing: bool,
    debug: bool,
) -> PromoterRecommendationResponse:
    scoring_config = promoter_recommendation_scoring_from_env()
    source, semantic_candidates = build_artist_semantic_candidates(
        connection,
        artist_id=artist_id,
        debug=False,
    )
    source_metadata = recommendation_item_metadata(connection, "artist", [artist_id])
    source_artist = source_metadata.get(artist_id)
    if source_artist is None:
        raise HTTPException(status_code=404, detail=f"Artist {artist_id} not found")

    candidate_scores = {
        item["entity_id"]: item["score"]
        for item in semantic_candidates[:500]
        if item["score"] > 0
    }
    artist_ids = list(candidate_scores.keys())
    artist_scores = [candidate_scores[artist_id] for artist_id in artist_ids]
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.artist_manual_connections') IS NOT NULL AS exists")
        manual_connections_table_exists = bool(cursor.fetchone()["exists"])
        if manual_connections_table_exists:
            manual_known_artists_cte = """
            manual_known_artists AS (
                SELECT
                    amc.connected_artist_id AS co_artist_id,
                    NULL::bigint AS shared_event_id
                FROM artist_manual_connections amc
                WHERE amc.source_artist_id = %(source_artist_id)s
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
            co_played_artists AS (
                SELECT DISTINCT
                    ea_shared.artist_id AS co_artist_id,
                    se.event_id AS shared_event_id
                FROM source_events se
                JOIN event_artists ea_shared
                    ON ea_shared.event_id = se.event_id
                WHERE ea_shared.artist_id <> %(source_artist_id)s
                UNION
                SELECT
                    mka.co_artist_id,
                    mka.shared_event_id
                FROM manual_known_artists mka
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
            candidate_promoters AS (
                SELECT promoter_id FROM semantic_promoters
                UNION
                SELECT promoter_id FROM direct_promoters
                UNION
                SELECT promoter_id FROM warm_promoters
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
                COALESCE(wp.warm_connection_artists, '[]'::jsonb) AS warm_connection_artists
            FROM candidate_promoters cp
            JOIN promoters p
                ON p.id = cp.promoter_id
            LEFT JOIN semantic_promoters sp
                ON sp.promoter_id = p.id
            LEFT JOIN direct_promoters dp
                ON dp.promoter_id = p.id
            LEFT JOIN warm_promoters wp
                ON wp.promoter_id = p.id
            ORDER BY semantic_score DESC, direct_connection_count DESC, warm_connection_count DESC, event_count DESC, p.id ASC
            LIMIT %(sql_candidate_limit)s
            """,
            {
                "artist_ids": artist_ids,
                "artist_scores": artist_scores,
                "source_artist_id": artist_id,
                "sql_candidate_limit": scoring_config.sql_candidate_limit,
            },
        )
        rows = cursor.fetchall()

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
    event_similarity_stats_by_promoter: dict[int, dict[str, object]] = {}
    for similar_row in similar_event_rows:
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
                SELECT id, name
                FROM promoters
                WHERE id = ANY(%s)
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
                    }
                )

    source_scale_stats = source_artist_scale_stats(connection, artist_id=artist_id)
    source_artist_event_count = max(int(source_scale_stats["event_count"]), 1)
    source_artist_scale = float(source_artist_event_count)

    recommendations = []
    exclude_existing_filtered_count = 0
    for row in rows:
        if exclude_existing and row["direct_connection_count"] > 0:
            exclude_existing_filtered_count += 1
            continue
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
        direct_connection_score = min(
            row["direct_connection_count"] / scoring_config.direct_connection_cap,
            1.0,
        )
        warm_network_score = min(
            row["warm_connection_count"] / scoring_config.warm_connection_cap,
            1.0,
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
        effective_event_count = max(row["event_count"], event_similarity_count)
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
        matched_artist_names_raw = row.get("matched_artist_names")
        matched_artist_names = (
            sorted({name.strip() for name in matched_artist_names_raw if isinstance(name, str) and name.strip()})
            if isinstance(matched_artist_names_raw, list)
            else []
        )
        related_event_titles_raw = row.get("related_event_titles")
        related_event_titles = (
            sorted(
                {
                    title.strip()
                    for title in related_event_titles_raw
                    if isinstance(title, str) and title.strip()
                }
            )
            if isinstance(related_event_titles_raw, list)
            else []
        )
        event_similarity_event_titles: list[str] = []
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
        related_event_titles = sorted(set(related_event_titles) | set(event_similarity_event_titles))
        row_with_similarity = {
            **row,
            "event_similarity_count": event_similarity_count,
            "event_count": effective_event_count,
            "latest_event_date": effective_latest_event_date,
            "warm_connection_artists": warm_connection_artists,
            "matched_artist_names": matched_artist_names,
            "event_similarity_event_titles": event_similarity_event_titles,
            "related_event_titles": related_event_titles,
        }
        direct_weight = 0.0 if exclude_existing else scoring_config.direct_connection_weight
        score_breakdown = {
            "semantic": scoring_config.semantic_weight * row["semantic_score"],
            "strength": scoring_config.strength_weight * strength_score,
            "directConnection": direct_weight * direct_connection_score,
            "warmNetwork": scoring_config.warm_network_weight * warm_network_score,
            "eventSimilarity": scoring_config.event_similarity_weight * event_similarity_score,
            "scaleFit": scoring_config.scale_fit_weight * scale_fit,
            "activity": scoring_config.activity_weight * activity_score,
            "recency": scoring_config.recency_weight * recency_score,
        }
        total_score = sum(score_breakdown.values())
        recommendations.append(
            PromoterRecommendationItem(
                id=row["id"],
                name=row["name"],
                score=total_score,
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
                directConnectionCount=row["direct_connection_count"],
                evidence=promoter_recommendation_item_evidence(row_with_similarity),
                debug={
                    "rawSignals": {
                        "semanticScore": row["semantic_score"],
                        "matchedArtistCount": row["matched_artist_count"],
                        "eventCount": effective_event_count,
                        "directConnectionCount": row["direct_connection_count"],
                        "warmConnectionCount": row["warm_connection_count"],
                        "eventSimilarityCount": event_similarity_count,
                        "eventSimilaritySymbolicScore": event_similarity_symbolic_score,
                        "eventSimilarityEmbeddingScore": event_similarity_embedding_score,
                        "artistScale": source_artist_scale,
                        "promoterScale": promoter_scale,
                        "artistScaleEventCount": source_artist_event_count,
                        "promoterScaleEventCount": effective_event_count,
                        "scaleBucketMultiplier": scale_bucket_multiplier,
                        "scaleFit": scale_fit,
                        "warmConnectionArtists": warm_connection_artists,
                    },
                    "normalizedScores": {
                        "strength": strength_score,
                        "directConnection": direct_connection_score,
                        "warmNetwork": warm_network_score,
                        "eventSimilarity": event_similarity_score,
                        "scaleFit": scale_fit,
                        "activity": activity_score,
                        "recency": recency_score,
                    },
                    "weightedScores": {
                        **score_breakdown,
                        "total": total_score,
                    },
                }
                if debug
                else None,
            )
        )

    sorted_recommendations = sorted(
        recommendations,
        key=lambda recommendation: (-recommendation.score, recommendation.id),
    )
    warm_recommendations_all = [
        recommendation
        for recommendation in sorted_recommendations
        if recommendation.warmConnectionCount > 0
    ]
    discovery_recommendations_all = [
        recommendation
        for recommendation in sorted_recommendations
        if recommendation.warmConnectionCount == 0
    ]
    warm_recommendations = warm_recommendations_all[:limit]
    remaining_slots = max(limit - len(warm_recommendations), 0)
    discovery_recommendations = discovery_recommendations_all[:remaining_slots]
    recommendations = [*warm_recommendations, *discovery_recommendations]
    recommendation_limit_cutoff = max(len(sorted_recommendations) - len(recommendations), 0)
    warm_limit_cutoff = max(len(warm_recommendations_all) - len(warm_recommendations), 0)
    discovery_limit_cutoff = max(len(discovery_recommendations_all) - len(discovery_recommendations), 0)
    if not recommendations:
        return PromoterRecommendationResponse(
            entityId=artist_id,
            model=source["model"],
            dimensions=source["dimensions"],
            recommendations=[],
            warmRecommendations=[],
            discoveryRecommendations=[],
            graph=GraphResponse(nodes=[], links=[]),
            debug={
                "candidateCounts": {
                    "sqlPromoterCandidates": len(rows),
                    "eventSimilarityPromotersAdded": len(additional_promoter_ids),
                    "warmCandidates": 0,
                    "discoveryCandidates": 0,
                    "recommendationsBeforeLimit": 0,
                    "returnedRecommendations": 0,
                    "returnedWarmRecommendations": 0,
                    "returnedDiscoveryRecommendations": 0,
                },
                "filteredOut": {
                    "excludeExisting": exclude_existing_filtered_count,
                    "eventSimilaritySamePromoter": similar_event_debug_counts["samePromoterFiltered"],
                    "eventSimilarityLimitCutoff": similar_event_debug_counts["similarityLimitCutoff"],
                    "recommendationLimitCutoff": 0,
                    "warmLimitCutoff": 0,
                    "discoveryLimitCutoff": 0,
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
    event_similarity_evidence: list[dict] = []
    for promoter_id in promoter_ids:
        similarity_stats = event_similarity_stats_by_promoter.get(promoter_id)
        if similarity_stats is None:
            continue
        ranked_rows = sorted(
            similarity_stats["rows"],
            key=lambda item: (-item["total_similarity_score"], item["candidate_event_id"]),
        )[:5]
        for item in ranked_rows:
            event_similarity_evidence.append(
                {
                    "promoter_id": promoter_id,
                    "source_event_id": item["source_event_id"],
                    "source_event_title": item["source_event_title"],
                    "source_event_date": item["source_event_date"],
                    "promoter_event_id": item["candidate_event_id"],
                    "promoter_event_title": item["candidate_event_title"],
                    "promoter_event_date": item["candidate_event_date"],
                    "promoter_venue_id": item["candidate_venue_id"],
                    "promoter_venue_name": item["candidate_venue_name"],
                    "path_similarity": item["symbolic_score_final"],
                }
            )

    return PromoterRecommendationResponse(
        entityId=artist_id,
        model=source["model"],
        dimensions=source["dimensions"],
        recommendations=recommendations,
        warmRecommendations=warm_recommendations,
        discoveryRecommendations=discovery_recommendations,
        graph=promoter_recommendation_graph(
            source_artist_id=artist_id,
            source_artist_name=source_artist["name"],
            recommendations=recommendations,
            semantic_evidence_rows=semantic_evidence,
            direct_evidence_rows=direct_evidence,
            warm_evidence_rows=warm_evidence,
            event_similarity_evidence_rows=event_similarity_evidence,
            scoring_config=scoring_config,
        ),
        debug={
            "candidateCounts": {
                "sqlPromoterCandidates": len(rows),
                "eventSimilarityPromotersAdded": len(additional_promoter_ids),
                "warmCandidates": len(warm_recommendations_all),
                "discoveryCandidates": len(discovery_recommendations_all),
                "recommendationsBeforeLimit": len(recommendations) + recommendation_limit_cutoff,
                "returnedRecommendations": len(recommendations),
                "returnedWarmRecommendations": len(warm_recommendations),
                "returnedDiscoveryRecommendations": len(discovery_recommendations),
            },
            "filteredOut": {
                "excludeExisting": exclude_existing_filtered_count,
                "eventSimilaritySamePromoter": similar_event_debug_counts["samePromoterFiltered"],
                "eventSimilarityLimitCutoff": similar_event_debug_counts["similarityLimitCutoff"],
                "recommendationLimitCutoff": recommendation_limit_cutoff,
                "warmLimitCutoff": warm_limit_cutoff,
                "discoveryLimitCutoff": discovery_limit_cutoff,
            },
        }
        if debug
        else None,
    )
