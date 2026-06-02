from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from app.db import get_db
from app.event_similarity import build_artist_similar_events_response
from app.recommendation_engine import build_similarity_response
from app.recommendation_scoring import promoter_recommendation_api_limit_max_from_env
from app.recommendation_services import (
    build_artist_promoter_recommendation_response,
    build_artist_recommendation_response,
    build_artist_semantic_response,
)
from app.schemas import (
    ArtistRecommendationResponse,
    ArtistSimilarEventsResponse,
    ArtistTagItem,
    ArtistTagsResponse,
    PromoterRecommendationResponse,
    SemanticArtistResponse,
    SimilarityResponse,
)

router = APIRouter()
PROMOTER_REC_API_LIMIT_MAX = promoter_recommendation_api_limit_max_from_env()


# Return semantic similar artists for a source artist.
@router.get(
    "/semantic/artists/{artist_id}",
    response_model=SemanticArtistResponse,
    response_model_exclude_none=True,
)
async def semantic_artists(
    artist_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    debug: bool = Query(default=False),
    connection: Connection = Depends(get_db),
) -> SemanticArtistResponse:
    return build_artist_semantic_response(
        connection,
        artist_id=artist_id,
        limit=limit,
        debug=debug,
    )


# Return extracted artist tags for inspection and debugging.
@router.get(
    "/artists/{artist_id}/tags",
    response_model=ArtistTagsResponse,
    response_model_exclude_none=True,
)
async def artist_tags(
    artist_id: int,
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0, alias="minConfidence"),
    connection: Connection = Depends(get_db),
) -> ArtistTagsResponse:
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

        cursor.execute(
            """
            SELECT
                tag_type,
                tag_value,
                source,
                confidence,
                extractor,
                evidence
            FROM artist_extracted_tags
            WHERE artist_id = %s
              AND confidence >= %s
            ORDER BY tag_type ASC, confidence DESC, tag_value ASC
            """,
            (artist_id, min_confidence),
        )
        tags = cursor.fetchall()

    return ArtistTagsResponse(
        artistId=artist["id"],
        artistName=artist["name"],
        tags=[
            ArtistTagItem(
                type=tag["tag_type"],
                value=tag["tag_value"],
                source=tag["source"],
                confidence=tag["confidence"],
                extractor=tag["extractor"],
                evidence=tag["evidence"],
            )
            for tag in tags
        ],
    )


# Backward-compatible alias for event similarity endpoint.
@router.get(
    "/recommendations/events/{event_id}",
    response_model=SimilarityResponse,
    response_model_exclude_none=True,
    include_in_schema=False,
)
async def recommend_events_alias(
    event_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    debug: bool = Query(default=False),
    exclude_same_promoter: bool = Query(default=True),
    connection: Connection = Depends(get_db),
) -> SimilarityResponse:
    return build_similarity_response(
        connection,
        entity_type="event",
        entity_id=event_id,
        limit=limit,
        debug=debug,
        exclude_same_promoter=exclude_same_promoter,
    )


# Return similar events for a given source event.
@router.get(
    "/recommendations/events/{event_id}/similar-events",
    response_model=SimilarityResponse,
    response_model_exclude_none=True,
)
async def recommend_similar_events(
    event_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    debug: bool = Query(default=False),
    exclude_same_promoter: bool = Query(default=True),
    connection: Connection = Depends(get_db),
) -> SimilarityResponse:
    return build_similarity_response(
        connection,
        entity_type="event",
        entity_id=event_id,
        limit=limit,
        debug=debug,
        exclude_same_promoter=exclude_same_promoter,
    )


# Return similar events for an artist history (analytics/helper endpoint).
@router.get(
    "/recommendations/artists/{artist_id}/similar-events",
    response_model=ArtistSimilarEventsResponse,
    response_model_exclude_none=True,
)
async def recommend_similar_events_for_artist(
    artist_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    debug: bool = Query(default=False),
    exclude_same_promoter: bool = Query(default=True),
    connection: Connection = Depends(get_db),
) -> ArtistSimilarEventsResponse:
    return build_artist_similar_events_response(
        connection,
        artist_id=artist_id,
        limit=limit,
        debug=debug,
        exclude_same_promoter=exclude_same_promoter,
    )


# Return main Artist -> Recommended Promoters response.
@router.get(
    "/recommendations/artists/{artist_id}/promoters",
    response_model=PromoterRecommendationResponse,
    response_model_exclude_none=True,
)
async def recommend_promoters_for_artist(
    artist_id: int,
    limit: int = Query(default=10, ge=1, le=PROMOTER_REC_API_LIMIT_MAX),
    exclude_existing: bool = Query(default=True),
    debug: bool = Query(default=False),
    connection: Connection = Depends(get_db),
) -> PromoterRecommendationResponse:
    return build_artist_promoter_recommendation_response(
        connection,
        artist_id=artist_id,
        limit=limit,
        exclude_existing=exclude_existing,
        debug=debug,
    )


# Return hybrid artist recommendations (legacy artist-to-artist endpoint).
@router.get(
    "/recommendations/artists/{artist_id}",
    response_model=ArtistRecommendationResponse,
    response_model_exclude_none=True,
)
async def recommend_artists(
    artist_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    connection: Connection = Depends(get_db),
) -> ArtistRecommendationResponse:
    return build_artist_recommendation_response(
        connection,
        artist_id=artist_id,
        limit=limit,
    )
