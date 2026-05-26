from __future__ import annotations

from psycopg import Connection

from app.embeddings import EmbeddingConfig, EntityType, rank_similar_embeddings
from app.event_similarity import event_style_tags_by_id
from app.recommendation_helpers import recommendation_item_metadata
from app.recommendation_scoring import (
    DEFAULT_RECOMMENDATION_SCORING,
    final_recommendation_score,
    hybrid_graph_score,
    is_similarity_candidate_eligible,
    recommendation_scoring_from_env,
)
from app.schemas import SimilarityItem, SimilarityResponse
from app.style_tags import extract_style_tags

# Normalize nullable id arrays from SQL into a set.
def as_id_set(values: list[int | None] | None) -> set[int]:
    """Normalize nullable integer lists from SQL rows into a set of ids."""
    return {int(value) for value in values or [] if value is not None}

# Build per-feature overlap diagnostics for debug output.
def similarity_graph_debug_components(
    *,
    entity_type: EntityType,
    source_features: dict[str, set[int]],
    candidate_features: dict[str, set[int]],
    scoring_config=DEFAULT_RECOMMENDATION_SCORING,
) -> dict[str, dict[str, object]]:
    """Build per-feature graph overlap diagnostics for debug responses."""
    weights = (
        scoring_config.event_graph_weights
        if entity_type == "event"
        else scoring_config.artist_graph_weights
    )
    components: dict[str, dict[str, object]] = {}
    public_feature_names = {
        "genres": "abstract_genres",
        "extracted_styles": "extracted_genres",
    }
    for weight in weights:
        source_values = source_features.get(weight.feature, set())
        candidate_values = candidate_features.get(weight.feature, set())
        overlap_count = len(source_values & candidate_values)

        if weight.boolean:
            normalized = 1.0 if overlap_count > 0 else 0.0
        else:
            if weight.cap is None:
                raise ValueError(f"Graph feature {weight.label} requires cap for non-boolean scoring")
            normalized = min(overlap_count / weight.cap, 1.0)

        public_key = public_feature_names.get(weight.feature, weight.feature)
        components[public_key] = {
            "weight": weight.weight,
            "overlapCount": overlap_count,
            "cap": weight.cap,
            "boolean": weight.boolean,
            "normalizedScore": normalized,
            "graphContribution": weight.weight * normalized,
        }
    return components

# Fetch core graph feature sets for artists or events.
def recommendation_feature_sets(
    connection: Connection,
    entity_type: EntityType,
    entity_ids: list[int],
) -> dict[int, dict[str, set[int]]]:
    """Fetch graph feature sets for a list of artists or events."""
    if not entity_ids:
        return {}

    if entity_type == "event":
        query = """
            SELECT
                e.id,
                array_remove(array_agg(DISTINCT ea.artist_id), NULL) AS artists,
                array_remove(array_agg(DISTINCT ep.promoter_id), NULL) AS promoters,
                array_remove(array_agg(DISTINCT eg.genre_id), NULL) AS genres,
                array_remove(ARRAY[e.venue_id], NULL) AS venues
            FROM events e
            LEFT JOIN event_artists ea
                ON ea.event_id = e.id
            LEFT JOIN event_promoters ep
                ON ep.event_id = e.id
            LEFT JOIN event_genres eg
                ON eg.event_id = e.id
            WHERE e.id = ANY(%s)
            GROUP BY e.id, e.venue_id
        """
    else:
        query = """
            SELECT
                a.id,
                array_remove(array_agg(DISTINCT ea.event_id), NULL) AS events,
                array_remove(array_agg(DISTINCT e.venue_id), NULL) AS venues,
                array_remove(array_agg(DISTINCT ep.promoter_id), NULL) AS promoters
            FROM artists a
            LEFT JOIN event_artists ea
                ON ea.artist_id = a.id
            LEFT JOIN events e
                ON e.id = ea.event_id
            LEFT JOIN event_promoters ep
                ON ep.event_id = ea.event_id
            WHERE a.id = ANY(%s)
            GROUP BY a.id
        """

    with connection.cursor() as cursor:
        cursor.execute(query, (entity_ids,))
        rows = cursor.fetchall()

    feature_sets = {
        row["id"]: {
            key: as_id_set(row.get(key))
            for key in ("artists", "events", "venues", "promoters")
        }
        for row in rows
    }
    if entity_type == "event":
        style_tags = event_style_tags_by_id(connection, entity_ids)
        for event_id, styles in style_tags.items():
            if event_id not in feature_sets:
                continue
            feature_sets[event_id]["extracted_styles"] = set(styles)  # type: ignore[assignment]
    else:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, COALESCE(biography_normalized, biography, '') AS biography
                FROM artists
                WHERE id = ANY(%s)
                """,
                (entity_ids,),
            )
            artist_rows = cursor.fetchall()
            cursor.execute("SELECT to_regclass('public.artist_extracted_tags') AS table_name")
            has_extracted_tags = cursor.fetchone()["table_name"] is not None

            extracted_style_tags_by_artist: dict[int, set[str]] = {}
            if has_extracted_tags:
                cursor.execute(
                    """
                    SELECT artist_id, tag_value
                    FROM artist_extracted_tags
                    WHERE artist_id = ANY(%s)
                      AND tag_type = 'style'
                      AND confidence >= 0.6
                    """,
                    (entity_ids,),
                )
                for row in cursor.fetchall():
                    artist_id = int(row["artist_id"])
                    tag = str(row["tag_value"]).strip().lower()
                    if not tag:
                        continue
                    extracted_style_tags_by_artist.setdefault(artist_id, set()).add(tag)

        for row in artist_rows:
            artist_id = int(row["id"])
            if artist_id not in feature_sets:
                continue
            biography_styles = set(extract_style_tags(row["biography"]))
            extracted_styles = extracted_style_tags_by_artist.get(artist_id, set())
            feature_sets[artist_id]["extracted_styles"] = biography_styles | extracted_styles  # type: ignore[assignment]
    return feature_sets

# Fetch candidate/source artist features excluding direct shared source events.
def artist_indirect_feature_sets(
    connection: Connection,
    *,
    source_artist_id: int,
    candidate_artist_ids: list[int],
) -> dict[int, dict[str, set[int]]]:
    """Fetch artist feature sets excluding direct source events for indirect scoring."""
    if not candidate_artist_ids:
        return {}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT event_id
            FROM event_artists
            WHERE artist_id = %s
            """,
            (source_artist_id,),
        )
        source_event_ids = [row["event_id"] for row in cursor.fetchall()]

    if not source_event_ids:
        return {}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH source_events AS (
                SELECT unnest(%(source_event_ids)s::bigint[]) AS event_id
            )
            SELECT
                a.id,
                array_remove(array_agg(DISTINCT ea.event_id), NULL) AS events,
                array_remove(array_agg(DISTINCT e.venue_id), NULL) AS venues,
                array_remove(array_agg(DISTINCT ep.promoter_id), NULL) AS promoters
            FROM artists a
            LEFT JOIN event_artists ea
                ON ea.artist_id = a.id
                AND NOT EXISTS (
                    SELECT 1
                    FROM source_events se
                    WHERE se.event_id = ea.event_id
                )
            LEFT JOIN events e
                ON e.id = ea.event_id
            LEFT JOIN event_promoters ep
                ON ep.event_id = ea.event_id
            WHERE a.id = ANY(%(candidate_artist_ids)s)
               OR a.id = %(source_artist_id)s
            GROUP BY a.id
            """,
            {
                "source_artist_id": source_artist_id,
                "source_event_ids": source_event_ids,
                "candidate_artist_ids": candidate_artist_ids,
            },
        )
        rows = cursor.fetchall()

    return {
        row["id"]: {
            key: as_id_set(row.get(key))
            for key in ("events", "venues", "promoters")
        }
        for row in rows
    }

# Apply indirect-only artist features for reranking context.
def apply_artist_indirect_features(
    connection: Connection,
    *,
    entity_type: EntityType,
    entity_id: int,
    candidate_ids: list[int],
    features: dict[int, dict[str, set[int]]],
) -> dict[int, dict[str, set[int]]]:
    """Apply indirect feature overrides for artist similarity reranking."""
    if entity_type != "artist":
        return features
    if entity_id not in features:
        return features

    indirect_features = artist_indirect_feature_sets(
        connection,
        source_artist_id=entity_id,
        candidate_artist_ids=candidate_ids,
    )
    if entity_id in indirect_features:
        for key in ("venues", "promoters"):
            features[entity_id][key] = indirect_features[entity_id].get(key, set())

    for candidate_id in candidate_ids:
        if candidate_id not in features or candidate_id not in indirect_features:
            continue
        for key in ("venues", "promoters"):
            features[candidate_id][key] = indirect_features[candidate_id].get(key, set())

    return features

# Rerank embedding candidates with graph and event-level adjustments.
def rerank_similar_entities(
    connection: Connection,
    *,
    entity_type: EntityType,
    entity_id: int,
    ranked: list[dict],
    limit: int,
    scoring_config=DEFAULT_RECOMMENDATION_SCORING,
) -> tuple[list[dict], dict[str, int]]:
    """Rerank embedding candidates with graph signals and event-specific adjustments."""
    candidate_ids = [item["entity_id"] for item in ranked]
    features = recommendation_feature_sets(connection, entity_type, [entity_id, *candidate_ids])
    features = apply_artist_indirect_features(
        connection,
        entity_type=entity_type,
        entity_id=entity_id,
        candidate_ids=candidate_ids,
        features=features,
    )
    source_features = features.get(entity_id)
    if not source_features:
        return ranked[:limit]
    interested_counts: dict[int, int] = {}
    if entity_type == "event":
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, COALESCE(interested_count, 0)::int AS interested_count
                FROM events
                WHERE id = ANY(%s)
                """,
                ([entity_id, *candidate_ids],),
            )
            interested_counts = {int(row["id"]): int(row["interested_count"]) for row in cursor.fetchall()}

    rescored = []
    missing_feature_count = 0
    ineligible_count = 0
    for item in ranked:
        candidate_features = features.get(item["entity_id"])
        if not candidate_features:
            missing_feature_count += 1
            continue

        graph_score, reasons = hybrid_graph_score(
            entity_type,
            source_features,
            candidate_features,
            config=scoring_config,
        )
        semantic_score = item["score"]
        if not is_similarity_candidate_eligible(
            entity_type,
            semantic_score,
            graph_score,
            scoring_config,
        ):
            ineligible_count += 1
            continue

        final_score = final_recommendation_score(
            semantic_score,
            graph_score,
            scoring_config,
        )
        event_rerank_adjustments: dict[str, float] = {}
        if entity_type == "event":
            extracted_overlap = len(source_features.get("extracted_styles", set()) & candidate_features.get("extracted_styles", set()))
            artist_overlap = len(source_features.get("artists", set()) & candidate_features.get("artists", set()))
            if graph_score < scoring_config.event_rerank_min_graph_for_neutral:
                event_rerank_adjustments["lowGraphPenalty"] = -scoring_config.event_rerank_low_graph_penalty
            if extracted_overlap >= scoring_config.event_rerank_extracted_genres_bonus_threshold:
                event_rerank_adjustments["extractedGenresBonus"] = scoring_config.event_rerank_extracted_genres_bonus
            if artist_overlap > 0:
                event_rerank_adjustments["sharedArtistsBonus"] = scoring_config.event_rerank_shared_artists_bonus
            source_interested_count = interested_counts.get(entity_id, 0)
            candidate_interested_count = interested_counts.get(item["entity_id"], 0)
            interested_relative_diff = None
            if source_interested_count > 0 and candidate_interested_count > 0:
                interested_relative_diff = (
                    abs(source_interested_count - candidate_interested_count)
                    / max(source_interested_count, candidate_interested_count)
                )
                if (
                    interested_relative_diff
                    <= scoring_config.event_rerank_interested_match_relative_diff_max
                ):
                    event_rerank_adjustments["interestedCountMatchBonus"] = (
                        scoring_config.event_rerank_interested_count_match_bonus
                    )
                elif (
                    interested_relative_diff
                    >= scoring_config.event_rerank_interested_mismatch_relative_diff_min
                ):
                    event_rerank_adjustments["interestedCountMismatchPenalty"] = (
                        -scoring_config.event_rerank_interested_count_mismatch_penalty
                    )
            final_score += sum(event_rerank_adjustments.values())
        rescored.append(
            {
                **item,
                "score": final_score,
                "semantic_score": semantic_score,
                "graph_score": graph_score,
                "reasons": reasons or ["semantic similarity"],
                "rerank_adjustments": event_rerank_adjustments if entity_type == "event" else {},
                "source_interested_count": interested_counts.get(entity_id) if entity_type == "event" else None,
                "candidate_interested_count": interested_counts.get(item["entity_id"]) if entity_type == "event" else None,
                "interested_count_relative_diff": interested_relative_diff if entity_type == "event" else None,
            }
        )

    sorted_rescored = sorted(
        rescored,
        key=lambda candidate: (-candidate["score"], candidate["entity_id"]),
    )
    debug_counts = {
        "embeddingCandidates": len(ranked),
        "missingFeatures": missing_feature_count,
        "ineligibleByThreshold": ineligible_count,
        "rerankedBeforeLimit": len(sorted_rescored),
        "rerankLimitCutoff": max(len(sorted_rescored) - limit, 0),
    }
    return sorted_rescored[:limit], debug_counts

# Build final similar-entities API response with optional debug details.
def build_similarity_response(
    connection: Connection,
    *,
    entity_type: EntityType,
    entity_id: int,
    limit: int,
    debug: bool = False,
    exclude_same_promoter: bool = False,
) -> SimilarityResponse:
    """Build API response for similar entities with optional debug diagnostics."""
    config = EmbeddingConfig.from_env()
    scoring_config = recommendation_scoring_from_env()
    overfetch_multiplier = 25 if entity_type == "event" and exclude_same_promoter else 10
    candidate_limit = 10_000 if entity_type == "artist" else max(limit * overfetch_multiplier, 200)
    source, ranked = rank_similar_embeddings(
        connection,
        entity_type=entity_type,
        entity_id=entity_id,
        config=config,
        limit=candidate_limit,
    )

    if source is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No {config.model} embedding found for {entity_type} {entity_id}. "
                "Run scripts/generate_embeddings.py first."
            ),
        )

    rerank_limit = max(limit * overfetch_multiplier, 200) if entity_type == "event" else limit
    reranked, rerank_debug_counts = rerank_similar_entities(
        connection,
        entity_type=entity_type,
        entity_id=entity_id,
        ranked=ranked,
        limit=rerank_limit,
        scoring_config=scoring_config,
    )
    metadata = recommendation_item_metadata(
        connection,
        entity_type,
        [item["entity_id"] for item in reranked],
    )
    candidate_ids = [item["entity_id"] for item in reranked if item["entity_id"] in metadata]
    feature_sets = recommendation_feature_sets(connection, entity_type, [entity_id, *candidate_ids])
    source_metadata = recommendation_item_metadata(connection, entity_type, [entity_id]).get(entity_id, {})
    source_features = feature_sets.get(entity_id, {})
    source_promoters = source_features.get("promoters", set())
    filtered_same_promoter_count = 0
    missing_metadata_count = 0
    similar: list[SimilarityItem] = []
    for item in reranked:
        candidate_id = item["entity_id"]
        if candidate_id not in metadata:
            missing_metadata_count += 1
            continue

        candidate_features = feature_sets.get(candidate_id, {})
        if (
            entity_type == "event"
            and exclude_same_promoter
            and bool(source_promoters & candidate_features.get("promoters", set()))
        ):
            filtered_same_promoter_count += 1
            continue

        score_breakdown = {
            "semantic": scoring_config.semantic_weight * item["semantic_score"],
            "graph": scoring_config.graph_weight * item["graph_score"],
        }
        dominant_signal: Literal["semantic", "graph", "mixed"]
        semantic_contribution = score_breakdown["semantic"]
        graph_contribution = score_breakdown["graph"]
        if semantic_contribution > graph_contribution * 1.15:
            dominant_signal = "semantic"
        elif graph_contribution > semantic_contribution * 1.15:
            dominant_signal = "graph"
        else:
            dominant_signal = "mixed"
        graph_components = similarity_graph_debug_components(
            entity_type=entity_type,
            source_features=source_features,
            candidate_features=candidate_features,
            scoring_config=scoring_config,
        )
        shared_extracted_styles: list[str] = []
        if entity_type == "event":
            source_styles = source_features.get("extracted_styles", set())
            candidate_styles = candidate_features.get("extracted_styles", set())
            shared_extracted_styles = sorted(source_styles & candidate_styles)[:10]
        similar.append(
            SimilarityItem(
                id=candidate_id,
                type=entity_type,
                name=metadata[candidate_id]["name"],
                score=item["score"],
                semanticScore=item["semantic_score"],
                graphScore=item["graph_score"],
                scoreBreakdown=score_breakdown,
                reasons=item["reasons"],
                date=metadata[candidate_id]["date"],
                venueName=metadata[candidate_id]["venue_name"],
                promoterId=metadata[candidate_id]["promoter_id"],
                promoterName=metadata[candidate_id]["promoter_name"],
                debug={
                    "raEventId": metadata[candidate_id].get("ra_event_id") if entity_type == "event" else None,
                    "sourceRaEventId": source_metadata.get("ra_event_id") if entity_type == "event" else None,
                    "rawSignals": {
                        "semanticScore": item["semantic_score"],
                        "graphScore": item["graph_score"],
                    },
                    "graphComponents": graph_components,
                    "sharedExtractedGenres": shared_extracted_styles if entity_type == "event" else None,
                    "sourceInterestedCount": item.get("source_interested_count") if entity_type == "event" else None,
                    "candidateInterestedCount": item.get("candidate_interested_count")
                    if entity_type == "event"
                    else None,
                    "interestedCountRelativeDiff": item.get("interested_count_relative_diff")
                    if entity_type == "event"
                    else None,
                    "dominantSignal": dominant_signal,
                    "rerankAdjustments": item.get("rerank_adjustments") if entity_type == "event" else None,
                    "weightedScores": {
                        **score_breakdown,
                        "adjustments": sum((item.get("rerank_adjustments") or {}).values()),
                        "total": item["score"],
                    },
                }
                if debug
                else None,
            )
        )

    response_limit_cutoff = max(len(similar) - limit, 0)
    similar = similar[:limit]

    return SimilarityResponse(
        entityId=entity_id,
        entityType=entity_type,
        model=source["model"],
        dimensions=source["dimensions"],
        similar=similar,
        debug={
            "candidateCounts": {
                "embeddingCandidates": len(ranked),
                "rerankedCandidates": len(reranked),
                "returnedCandidates": len(similar),
            },
            "filteredOut": {
                "missingFeatures": rerank_debug_counts["missingFeatures"],
                "ineligibleByThreshold": rerank_debug_counts["ineligibleByThreshold"],
                "rerankLimitCutoff": rerank_debug_counts["rerankLimitCutoff"],
                "missingMetadata": missing_metadata_count,
                "samePromoter": filtered_same_promoter_count,
                "responseLimitCutoff": response_limit_cutoff,
            },
        }
        if debug
        else None,
    )
