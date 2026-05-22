from __future__ import annotations

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
        cursor.execute(
            """
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
                    count(DISTINCT e.id)::int AS event_count,
                    max(sc.semantic_score)::double precision AS semantic_score,
                    max(e.event_date)::date AS latest_event_date
                FROM semantic_candidates sc
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
                    count(DISTINCT e.id)::int AS warm_event_count,
                    max(e.event_date)::date AS latest_warm_event_date
                FROM co_played_artists cpa
                JOIN event_artists ea
                    ON ea.artist_id = cpa.co_artist_id
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                WHERE e.id <> cpa.shared_event_id
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
                GREATEST(
                    COALESCE(sp.event_count, 0),
                    COALESCE(dp.direct_connection_count, 0),
                    COALESCE(wp.warm_event_count, 0)
                )::int AS event_count,
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
                COALESCE(wp.warm_connection_count, 0)::int AS warm_connection_count
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
            LIMIT 200
            """,
            {
                "artist_ids": artist_ids,
                "artist_scores": artist_scores,
                "source_artist_id": artist_id,
            },
        )
        rows = cursor.fetchall()

    similar_event_rows, _, similar_event_debug_counts = artist_similar_events_scored_rows(
        connection,
        source_artist_id=artist_id,
        limit=max(limit * 20, 500),
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
                        "event_count": 0,
                        "semantic_score": 0.0,
                        "latest_event_date": None,
                        "direct_connection_count": 0,
                        "warm_connection_count": 0,
                    }
                )

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
        row_with_similarity = {
            **row,
            "event_similarity_count": event_similarity_count,
            "event_count": effective_event_count,
            "latest_event_date": effective_latest_event_date,
        }
        direct_weight = 0.0 if exclude_existing else scoring_config.direct_connection_weight
        score_breakdown = {
            "semantic": scoring_config.semantic_weight * row["semantic_score"],
            "strength": scoring_config.strength_weight * strength_score,
            "directConnection": direct_weight * direct_connection_score,
            "warmNetwork": scoring_config.warm_network_weight * warm_network_score,
            "eventSimilarity": scoring_config.event_similarity_weight * event_similarity_score,
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
                    },
                    "normalizedScores": {
                        "strength": strength_score,
                        "directConnection": direct_connection_score,
                        "warmNetwork": warm_network_score,
                        "eventSimilarity": event_similarity_score,
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

    recommendation_limit_cutoff = max(len(recommendations) - limit, 0)
    recommendations = sorted(
        recommendations,
        key=lambda recommendation: (-recommendation.score, recommendation.id),
    )[:limit]
    if not recommendations:
        return PromoterRecommendationResponse(
            entityId=artist_id,
            model=source["model"],
            dimensions=source["dimensions"],
            recommendations=[],
            graph=GraphResponse(nodes=[], links=[]),
            debug={
                "candidateCounts": {
                    "sqlPromoterCandidates": len(rows),
                    "eventSimilarityPromotersAdded": len(additional_promoter_ids),
                    "recommendationsBeforeLimit": 0,
                    "returnedRecommendations": 0,
                },
                "filteredOut": {
                    "excludeExisting": exclude_existing_filtered_count,
                    "eventSimilaritySamePromoter": similar_event_debug_counts["samePromoterFiltered"],
                    "eventSimilarityLimitCutoff": similar_event_debug_counts["similarityLimitCutoff"],
                    "recommendationLimitCutoff": 0,
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
                "recommendationsBeforeLimit": len(recommendations) + recommendation_limit_cutoff,
                "returnedRecommendations": len(recommendations),
            },
            "filteredOut": {
                "excludeExisting": exclude_existing_filtered_count,
                "eventSimilaritySamePromoter": similar_event_debug_counts["samePromoterFiltered"],
                "eventSimilarityLimitCutoff": similar_event_debug_counts["similarityLimitCutoff"],
                "recommendationLimitCutoff": recommendation_limit_cutoff,
            },
        }
        if debug
        else None,
    )


