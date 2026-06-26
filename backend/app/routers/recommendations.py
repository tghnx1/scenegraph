from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_connection
from app.auth import get_current_user_id
from app.recommendation_scoring import promoter_recommendation_api_limit_max_from_env
from app.recommendation_services import build_artist_promoter_recommendation_response
from app.schemas import ArtistTagItem, ArtistTagsResponse, PromoterRecommendationResponse

router = APIRouter()
PROMOTER_REC_API_LIMIT_MAX = promoter_recommendation_api_limit_max_from_env()




# Return extracted artist tags for inspection and debugging.
@router.get(
    "/artists/{artist_id}/tags",
    response_model=ArtistTagsResponse,
    response_model_exclude_none=True,
)
async def artist_tags(
    artist_id: int,
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0, alias="minConfidence"),
) -> ArtistTagsResponse:
    with get_connection() as connection:
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
    user_id: int = Depends(get_current_user_id),
) -> PromoterRecommendationResponse:
    with get_connection() as connection:
        return build_artist_promoter_recommendation_response(
            connection,
            artist_id=artist_id,
            limit=limit,
            exclude_existing=exclude_existing,
            debug=debug,
            user_id=user_id,
        )
