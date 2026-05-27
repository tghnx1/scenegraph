from __future__ import annotations

from fastapi import HTTPException
from psycopg import Connection

from app.embeddings import EmbeddingConfig, cosine_similarity, embedding_vector_supported
from app.recommendation_scoring import (
    PromoterRecommendationScoringConfig,
    promoter_recommendation_scoring_from_env,
)
from app.schemas import ArtistSimilarEventItem, ArtistSimilarEventsResponse
from app.style_tags import extract_style_tags

# Build scored similar-event rows for a source artist.
def artist_similar_events_scored_rows(
    connection: Connection,
    *,
    source_artist_id: int,
    limit: int,
    exclude_same_promoter: bool,
    scoring_config: PromoterRecommendationScoringConfig,
    collect_debug: bool = False,
) -> tuple[list[dict], int | None, dict[str, int]]:
    """Collect and score similar-event rows for an artist using symbolic+embedding blend."""
    same_promoter_filtered_count = 0
    if collect_debug and exclude_same_promoter:
        same_promoter_filtered_count = artist_event_similarity_same_promoter_filtered_count(
            connection,
            source_artist_id=source_artist_id,
            scoring_config=scoring_config,
        )
    candidate_rows = artist_event_similarity_candidates(
        connection,
        source_artist_id=source_artist_id,
        limit=max(limit, 1),
        exclude_same_promoter=exclude_same_promoter,
        scoring_config=scoring_config,
    )
    if not candidate_rows:
        return [], None, {
            "candidateRowsFetched": 0,
            "samePromoterFiltered": same_promoter_filtered_count,
            "similarityLimitCutoff": 0,
        }

    source_event_ids = sorted({int(row["source_event_id"]) for row in candidate_rows})
    candidate_event_ids = [int(row["candidate_event_id"]) for row in candidate_rows]
    event_styles = event_style_tags_by_id(connection, source_event_ids + candidate_event_ids)
    embedding_scores, embedding_dimensions = event_embedding_similarity_by_candidate(
        connection,
        source_event_ids=source_event_ids,
        candidate_event_ids=candidate_event_ids,
    )

    scored_rows: list[dict] = []
    for row in candidate_rows:
        source_styles = event_styles.get(int(row["source_event_id"]), set())
        candidate_styles = event_styles.get(int(row["candidate_event_id"]), set())
        shared_extracted_genres = sorted(source_styles & candidate_styles)
        extracted_style_score = (
            scoring_config.event_similarity_extracted_style_weight if shared_extracted_genres else 0.0
        )
        symbolic_score = min(float(row["symbolic_score"]) + extracted_style_score, 1.0)
        embedding_score = float(embedding_scores.get(row["candidate_event_id"], 0.0))
        weighted_symbolic_score = scoring_config.event_similarity_symbolic_weight * symbolic_score
        weighted_embedding_score = scoring_config.event_similarity_embedding_weight * embedding_score

        scored_rows.append(
            {
                **row,
                "shared_extracted_genres": shared_extracted_genres,
                "extracted_style_score": extracted_style_score,
                "symbolic_score_final": symbolic_score,
                "embedding_score": embedding_score,
                "weighted_symbolic_score": weighted_symbolic_score,
                "weighted_embedding_score": weighted_embedding_score,
                "total_similarity_score": weighted_symbolic_score + weighted_embedding_score,
            }
        )

    scored_rows.sort(
        key=lambda item: (-item["total_similarity_score"], item["candidate_event_id"]),
    )
    return scored_rows[:limit], embedding_dimensions, {
        "candidateRowsFetched": len(candidate_rows),
        "samePromoterFiltered": same_promoter_filtered_count,
        "similarityLimitCutoff": max(len(scored_rows) - limit, 0),
    }

# Compute candidate event embedding similarity against source events.
def event_embedding_similarity_by_candidate(
    connection: Connection,
    *,
    source_event_ids: list[int],
    candidate_event_ids: list[int],
) -> tuple[dict[int, float], int | None]:
    """Compute max cosine similarity from candidate event to any source event embedding."""
    if not source_event_ids or not candidate_event_ids:
        return {}, None

    config = EmbeddingConfig.from_env()
    if embedding_vector_supported(connection):
        dimensions_filter = ""
        params: list[object] = [
            source_event_ids,
            config.provider_model_key,
        ]
        if config.dimensions is not None:
            dimensions_filter = "AND dimensions = %s"
            params.append(config.dimensions)
        params.extend((candidate_event_ids, config.provider_model_key))
        if config.dimensions is not None:
            params.append(config.dimensions)

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                WITH source_embeddings AS (
                    SELECT DISTINCT ON (entity_id)
                        entity_id,
                        dimensions,
                        embedding_vec
                    FROM entity_embeddings
                    WHERE entity_type = 'event'
                      AND entity_id = ANY(%s)
                      AND model = %s
                      AND embedding_vec IS NOT NULL
                      {dimensions_filter}
                    ORDER BY entity_id ASC, updated_at DESC
                ),
                candidate_embeddings AS (
                    SELECT DISTINCT ON (entity_id)
                        entity_id,
                        dimensions,
                        embedding_vec
                    FROM entity_embeddings
                    WHERE entity_type = 'event'
                      AND entity_id = ANY(%s)
                      AND model = %s
                      AND embedding_vec IS NOT NULL
                      {dimensions_filter}
                    ORDER BY entity_id ASC, updated_at DESC
                ),
                scored_candidates AS (
                    SELECT
                        c.entity_id AS candidate_event_id,
                        max(
                            GREATEST(
                                1 - (s.embedding_vec <=> c.embedding_vec),
                                0.0
                            )
                        )::double precision AS score
                    FROM candidate_embeddings c
                    JOIN source_embeddings s
                        ON s.dimensions = c.dimensions
                    GROUP BY c.entity_id
                ),
                source_dims AS (
                    SELECT max(dimensions)::int AS dimensions
                    FROM source_embeddings
                )
                SELECT
                    sc.candidate_event_id,
                    sc.score,
                    sd.dimensions
                FROM scored_candidates sc
                CROSS JOIN source_dims sd
                """,
                params,
            )
            rows = cursor.fetchall()

        if not rows:
            return {}, config.dimensions

        dimensions = rows[0].get("dimensions")
        scores = {
            int(row["candidate_event_id"]): float(row["score"])
            for row in rows
            if row["candidate_event_id"] is not None
        }
        return scores, int(dimensions) if dimensions is not None else config.dimensions

    target_event_ids = set(source_event_ids) | set(candidate_event_ids)
    dimensions_filter = ""
    params: list[object] = ["event", list(target_event_ids), config.provider_model_key]
    if config.dimensions is not None:
        dimensions_filter = "AND dimensions = %s"
        params.append(config.dimensions)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT DISTINCT ON (entity_id)
                entity_id,
                embedding
            FROM entity_embeddings
            WHERE entity_type = %s
              AND entity_id = ANY(%s)
              AND model = %s
              {dimensions_filter}
            ORDER BY entity_id ASC, updated_at DESC
            """,
            params,
        )
        embedding_rows = cursor.fetchall()

    dimensions: int | None = None
    embeddings_by_event_id: dict[int, list[float]] = {}
    for row in embedding_rows:
        event_embedding = row["embedding"]
        if dimensions is None:
            dimensions = len(event_embedding)
        embeddings_by_event_id[int(row["entity_id"])] = event_embedding

    source_vectors = [
        embeddings_by_event_id[event_id]
        for event_id in source_event_ids
        if event_id in embeddings_by_event_id
    ]
    if not source_vectors:
        return {}, dimensions

    scores: dict[int, float] = {}
    for event_id in candidate_event_ids:
        target_vector = embeddings_by_event_id.get(event_id)
        if target_vector is None:
            continue
        scores[event_id] = max(
            max(cosine_similarity(source_vector, target_vector), 0.0) for source_vector in source_vectors
        )
    return scores, dimensions

# Extract normalized style tags for a set of events.
def event_style_tags_by_id(connection: Connection, event_ids: list[int]) -> dict[int, set[str]]:
    """Extract normalized style/genre tags from event title + description + lineup text."""
    if not event_ids:
        return {}

    unique_event_ids = sorted(set(event_ids))
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                e.id,
                e.title,
                e.description_text,
                e.lineup_raw,
                e.lineup_residual_text
            FROM events e
            WHERE e.id = ANY(%s)
            """,
            (unique_event_ids,),
        )
        rows = cursor.fetchall()

    styles_by_event_id: dict[int, set[str]] = {}
    for row in rows:
        style_input = " ".join(
            part
            for part in (
                row.get("title"),
                row.get("description_text"),
                row.get("lineup_residual_text") or row.get("lineup_raw"),
            )
            if part
        )
        styles_by_event_id[int(row["id"])] = set(extract_style_tags(style_input))
    return styles_by_event_id

# Fetch symbolic event-similarity candidates for an artist.
def artist_event_similarity_candidates(
    connection: Connection,
    *,
    source_artist_id: int,
    limit: int,
    exclude_same_promoter: bool,
    scoring_config: PromoterRecommendationScoringConfig,
) -> list[dict]:
    """Fetch raw symbolic similarity candidates between source-artist events and other events."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH source_events AS (
                SELECT DISTINCT
                    e.id AS source_event_id,
                    e.title AS source_event_title,
                    e.event_date::date AS source_event_date,
                    e.venue_id AS source_venue_id
                FROM event_artists ea
                JOIN events e
                    ON e.id = ea.event_id
                WHERE ea.artist_id = %(source_artist_id)s
            ),
            source_promoters AS (
                SELECT DISTINCT ep.promoter_id
                FROM source_events se
                JOIN event_promoters ep
                    ON ep.event_id = se.source_event_id
            ),
            similarity_paths AS (
                SELECT
                    se.source_event_id,
                    se.source_event_title,
                    se.source_event_date,
                    e.id AS candidate_event_id,
                    e.title AS candidate_event_title,
                    e.event_date::date AS candidate_event_date,
                    e.venue_id AS candidate_venue_id,
                    v.name AS candidate_venue_name,
                    promoter.promoter_id,
                    promoter.promoter_name,
                    CASE WHEN e.venue_id IS NOT NULL AND e.venue_id = se.source_venue_id THEN 1.0 ELSE 0.0 END
                        AS same_venue_score,
                    (
                        SELECT count(DISTINCT eg_source.genre_id)::int
                        FROM event_genres eg_source
                        JOIN event_genres eg_candidate
                          ON eg_candidate.genre_id = eg_source.genre_id
                        WHERE eg_source.event_id = se.source_event_id
                          AND eg_candidate.event_id = e.id
                    ) AS shared_genre_count,
                    (
                        SELECT count(DISTINCT ea_source.artist_id)::int
                        FROM event_artists ea_source
                        JOIN event_artists ea_candidate
                          ON ea_candidate.artist_id = ea_source.artist_id
                        WHERE ea_source.event_id = se.source_event_id
                          AND ea_candidate.event_id = e.id
                          AND ea_source.artist_id <> %(source_artist_id)s
                    ) AS shared_lineup_count
                FROM source_events se
                JOIN events e
                    ON e.id <> se.source_event_id
                LEFT JOIN venues v
                    ON v.id = e.venue_id
                LEFT JOIN LATERAL (
                    SELECT
                        p.id AS promoter_id,
                        p.name AS promoter_name
                    FROM event_promoters ep
                    JOIN promoters p
                        ON p.id = ep.promoter_id
                    WHERE ep.event_id = e.id
                    ORDER BY p.id ASC
                    LIMIT 1
                ) promoter
                    ON true
                WHERE (
                    NOT %(exclude_same_promoter)s
                    OR NOT EXISTS (
                        SELECT 1
                        FROM event_promoters ep_same
                        JOIN source_promoters sp
                            ON sp.promoter_id = ep_same.promoter_id
                        WHERE ep_same.event_id = e.id
                    )
                )
            ),
            scored_paths AS (
                SELECT
                    *,
                    (
                        %(same_venue_weight)s * same_venue_score
                        + %(shared_genre_weight)s * CASE WHEN shared_genre_count > 0 THEN 1.0 ELSE 0.0 END
                        + %(shared_lineup_weight)s * CASE WHEN shared_lineup_count > 0 THEN 1.0 ELSE 0.0 END
                    )::double precision AS symbolic_score
                FROM similarity_paths
            ),
            matched_paths AS (
                SELECT *
                FROM scored_paths
                WHERE symbolic_score > 0
            ),
            ranked_paths AS (
                SELECT
                    *,
                    row_number() OVER (
                        PARTITION BY candidate_event_id
                        ORDER BY symbolic_score DESC, source_event_date DESC NULLS LAST, source_event_id DESC
                    ) AS row_number
                FROM matched_paths
            )
            SELECT *
            FROM ranked_paths
            WHERE row_number = 1
            ORDER BY symbolic_score DESC, candidate_event_date DESC NULLS LAST, candidate_event_id DESC
            LIMIT %(limit)s
            """,
            {
                "source_artist_id": source_artist_id,
                "limit": max(limit, 1),
                "exclude_same_promoter": exclude_same_promoter,
                "same_venue_weight": scoring_config.event_similarity_same_venue_weight,
                "shared_genre_weight": scoring_config.event_similarity_shared_genre_weight,
                "shared_lineup_weight": scoring_config.event_similarity_shared_lineup_weight,
            },
        )
        return cursor.fetchall()

# Count how many candidates are filtered by same-promoter exclusion.
def artist_event_similarity_same_promoter_filtered_count(
    connection: Connection,
    *,
    source_artist_id: int,
    scoring_config: PromoterRecommendationScoringConfig,
) -> int:
    """Count event candidates removed solely because they share source promoters."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH source_events AS (
                SELECT DISTINCT
                    e.id AS source_event_id,
                    e.venue_id AS source_venue_id
                FROM event_artists ea
                JOIN events e
                    ON e.id = ea.event_id
                WHERE ea.artist_id = %(source_artist_id)s
            ),
            source_promoters AS (
                SELECT DISTINCT ep.promoter_id
                FROM source_events se
                JOIN event_promoters ep
                    ON ep.event_id = se.source_event_id
            ),
            similarity_paths AS (
                SELECT
                    se.source_event_id,
                    e.id AS candidate_event_id,
                    (
                        CASE WHEN e.venue_id IS NOT NULL AND e.venue_id = se.source_venue_id THEN 1.0 ELSE 0.0 END
                    ) AS same_venue_score,
                    (
                        SELECT count(DISTINCT eg_source.genre_id)::int
                        FROM event_genres eg_source
                        JOIN event_genres eg_candidate
                          ON eg_candidate.genre_id = eg_source.genre_id
                        WHERE eg_source.event_id = se.source_event_id
                          AND eg_candidate.event_id = e.id
                    ) AS shared_genre_count,
                    (
                        SELECT count(DISTINCT ea_source.artist_id)::int
                        FROM event_artists ea_source
                        JOIN event_artists ea_candidate
                          ON ea_candidate.artist_id = ea_source.artist_id
                        WHERE ea_source.event_id = se.source_event_id
                          AND ea_candidate.event_id = e.id
                          AND ea_source.artist_id <> %(source_artist_id)s
                    ) AS shared_lineup_count,
                    EXISTS (
                        SELECT 1
                        FROM event_promoters ep_same
                        JOIN source_promoters sp
                            ON sp.promoter_id = ep_same.promoter_id
                        WHERE ep_same.event_id = e.id
                    ) AS shares_source_promoter
                FROM source_events se
                JOIN events e
                    ON e.id <> se.source_event_id
            ),
            scored_paths AS (
                SELECT
                    *,
                    (
                        %(same_venue_weight)s * same_venue_score
                        + %(shared_genre_weight)s * CASE WHEN shared_genre_count > 0 THEN 1.0 ELSE 0.0 END
                        + %(shared_lineup_weight)s * CASE WHEN shared_lineup_count > 0 THEN 1.0 ELSE 0.0 END
                    )::double precision AS symbolic_score
                FROM similarity_paths
            ),
            matched_paths AS (
                SELECT *
                FROM scored_paths
                WHERE symbolic_score > 0
            ),
            ranked_paths AS (
                SELECT
                    *,
                    row_number() OVER (
                        PARTITION BY candidate_event_id
                        ORDER BY symbolic_score DESC, source_event_id DESC
                    ) AS row_number
                FROM matched_paths
            )
            SELECT count(*)::int AS filtered_count
            FROM ranked_paths
            WHERE row_number = 1
              AND shares_source_promoter
            """,
            {
                "source_artist_id": source_artist_id,
                "same_venue_weight": scoring_config.event_similarity_same_venue_weight,
                "shared_genre_weight": scoring_config.event_similarity_shared_genre_weight,
                "shared_lineup_weight": scoring_config.event_similarity_shared_lineup_weight,
            },
        )
        row = cursor.fetchone()
    return int(row["filtered_count"]) if row else 0

# Build artist similar-events API response.
def build_artist_similar_events_response(
    connection: Connection,
    *,
    artist_id: int,
    limit: int,
    debug: bool,
    exclude_same_promoter: bool,
) -> ArtistSimilarEventsResponse:
    """Build artist->similar-events response with blended symbolic and semantic signals."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name
            FROM artists
            WHERE id = %s
            """,
            (artist_id,),
        )
        artist = cursor.fetchone()
    if artist is None:
        raise HTTPException(status_code=404, detail=f"Artist {artist_id} not found")

    config = EmbeddingConfig.from_env()
    scoring_config = promoter_recommendation_scoring_from_env()
    scored_rows, embedding_dimensions, similar_events_debug_counts = artist_similar_events_scored_rows(
        connection,
        source_artist_id=artist_id,
        limit=max(limit * 20, 200),
        exclude_same_promoter=exclude_same_promoter,
        scoring_config=scoring_config,
        collect_debug=debug,
    )
    if not scored_rows:
        return ArtistSimilarEventsResponse(
            entityId=artist_id,
            model=config.provider_model_key,
            dimensions=config.dimensions,
            similarEvents=[],
            debug={
                "candidateCounts": {
                    "scoredCandidates": 0,
                    "returnedCandidates": 0,
                },
                "filteredOut": {
                    "samePromoter": similar_events_debug_counts["samePromoterFiltered"],
                    "similarityLimitCutoff": similar_events_debug_counts["similarityLimitCutoff"],
                    "responseLimitCutoff": 0,
                },
            }
            if debug
            else None,
        )

    similar_events: list[ArtistSimilarEventItem] = []
    for row in scored_rows:
        score_breakdown = {
            "symbolic": row["weighted_symbolic_score"],
            "embedding": row["weighted_embedding_score"],
        }
        reasons: list[str] = []
        if row["same_venue_score"] > 0:
            reasons.append("same venue as one of your events")
        if row["shared_genre_count"] > 0:
            reasons.append(f"shares {row['shared_genre_count']} abstract genres with your event history")
        if row["shared_extracted_genres"]:
            reasons.append(
                f"{len(row['shared_extracted_genres'])} shared extracted genres: "
                f"{', '.join(row['shared_extracted_genres'][:5])}"
            )
        if row["shared_lineup_count"] > 0:
            reasons.append(f"shares {row['shared_lineup_count']} lineup artists with your events")
        if row["embedding_score"] >= 0.6:
            reasons.append("high semantic event profile similarity")

        similar_events.append(
            ArtistSimilarEventItem(
                id=row["candidate_event_id"],
                name=row["candidate_event_title"],
                score=row["total_similarity_score"],
                scoreBreakdown=score_breakdown,
                eventDate=row["candidate_event_date"],
                venueName=row["candidate_venue_name"],
                promoterId=row["promoter_id"],
                promoterName=row["promoter_name"],
                sourceEventId=row["source_event_id"],
                sourceEventName=row["source_event_title"],
                sourceEventDate=row["source_event_date"],
                reasons=reasons[:4] if reasons else ["event-level scene overlap"],
                debug={
                    "components": {
                        "sameVenueScore": row["same_venue_score"],
                        "sharedGenreCount": row["shared_genre_count"],
                        "sharedExtractedGenres": row["shared_extracted_genres"],
                        "sharedLineupCount": row["shared_lineup_count"],
                        "extractedStyleScore": row["extracted_style_score"],
                        "symbolicScore": row["symbolic_score_final"],
                        "embeddingScore": row["embedding_score"],
                    },
                    "weights": {
                        "symbolic": scoring_config.event_similarity_symbolic_weight,
                        "embedding": scoring_config.event_similarity_embedding_weight,
                    },
                    "weightedScores": {
                        "symbolic": score_breakdown["symbolic"],
                        "embedding": score_breakdown["embedding"],
                        "total": sum(score_breakdown.values()),
                    },
                }
                if debug
                else None,
            )
        )

    response_limit_cutoff = max(len(similar_events) - limit, 0)
    similar_events = sorted(
        similar_events,
        key=lambda item: (-item.score, item.id),
    )[:limit]
    return ArtistSimilarEventsResponse(
        entityId=artist_id,
        model=config.provider_model_key,
        dimensions=embedding_dimensions if embedding_dimensions is not None else config.dimensions,
        similarEvents=similar_events,
        debug={
            "candidateCounts": {
                "scoredCandidates": similar_events_debug_counts["candidateRowsFetched"],
                "returnedCandidates": len(similar_events),
            },
            "filteredOut": {
                "samePromoter": similar_events_debug_counts["samePromoterFiltered"],
                "similarityLimitCutoff": similar_events_debug_counts["similarityLimitCutoff"],
                "responseLimitCutoff": response_limit_cutoff,
            },
        }
        if debug
        else None,
    )
