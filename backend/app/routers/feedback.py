from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user_id
from app.db import get_connection
from app.recommendations.helpers import ensure_feedback_entity_exists, feedback_item_from_row
from app.schemas import (
    FeedbackCandidateKind,
    FeedbackSourceKind,
    RecommendationFeedbackItem,
    RecommendationFeedbackRequest,
    RecommendationFeedbackResponse,
)

router = APIRouter()


@router.post(
    "/recommendation-feedback",
    response_model=RecommendationFeedbackItem,
    response_model_exclude_none=True,
)
async def upsert_recommendation_feedback(
    request: RecommendationFeedbackRequest,
    user_id: int = Depends(get_current_user_id),
) -> RecommendationFeedbackItem:
    with get_connection() as connection:
        ensure_feedback_entity_exists(
            connection,
            entity_type=request.sourceEntityType,
            entity_id=request.sourceEntityId,
        )
        ensure_feedback_entity_exists(
            connection,
            entity_type=request.candidateEntityType,
            entity_id=request.candidateEntityId,
        )

        reason = request.reason.strip() if request.reason else None
        if reason == "":
            reason = None

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO recommendation_feedback (
                    user_id,
                    source_entity_type,
                    source_entity_id,
                    candidate_entity_type,
                    candidate_entity_id,
                    feedback,
                    reason
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (
                    user_id,
                    source_entity_type,
                    source_entity_id,
                    candidate_entity_type,
                    candidate_entity_id
                )
                DO UPDATE SET
                    feedback = EXCLUDED.feedback,
                    reason = EXCLUDED.reason,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING
                    id,
                    user_id,
                    source_entity_type,
                    source_entity_id,
                    candidate_entity_type,
                    candidate_entity_id,
                    feedback,
                    reason,
                    created_at,
                    updated_at
                """,
                (
                    user_id,
                    request.sourceEntityType,
                    request.sourceEntityId,
                    request.candidateEntityType,
                    request.candidateEntityId,
                    request.feedback,
                    reason,
                ),
            )
            row = cursor.fetchone()

    return feedback_item_from_row(row)


@router.get(
    "/recommendation-feedback",
    response_model=RecommendationFeedbackResponse,
    response_model_exclude_none=True,
)
async def list_recommendation_feedback(
    source_entity_type: FeedbackSourceKind | None = Query(default=None, alias="sourceEntityType"),
    source_entity_id: int | None = Query(default=None, ge=1, alias="sourceEntityId"),
    candidate_entity_type: FeedbackCandidateKind | None = Query(default=None, alias="candidateEntityType"),
    candidate_entity_id: int | None = Query(default=None, ge=1, alias="candidateEntityId"),
    user_id: int = Depends(get_current_user_id),
) -> RecommendationFeedbackResponse:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    user_id,
                    source_entity_type,
                    source_entity_id,
                    candidate_entity_type,
                    candidate_entity_id,
                    feedback,
                    reason,
                    created_at,
                    updated_at
                FROM recommendation_feedback
                WHERE user_id = %s
                  AND (%s::text IS NULL OR source_entity_type = %s)
                  AND (%s::bigint IS NULL OR source_entity_id = %s)
                  AND (%s::text IS NULL OR candidate_entity_type = %s)
                  AND (%s::bigint IS NULL OR candidate_entity_id = %s)
                ORDER BY updated_at DESC, id DESC
                LIMIT 500
                """,
                (
                    user_id,
                    source_entity_type,
                    source_entity_type,
                    source_entity_id,
                    source_entity_id,
                    candidate_entity_type,
                    candidate_entity_type,
                    candidate_entity_id,
                    candidate_entity_id,
                ),
            )
            rows = cursor.fetchall()

    return RecommendationFeedbackResponse(
        feedback=[feedback_item_from_row(row) for row in rows],
    )


@router.delete(
    "/recommendation-feedback/{feedback_id}",
    response_model=RecommendationFeedbackItem,
    response_model_exclude_none=True,
)
async def delete_recommendation_feedback(
    feedback_id: int,
    user_id: int = Depends(get_current_user_id),
) -> RecommendationFeedbackItem:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM recommendation_feedback
                WHERE id = %s
                  AND user_id = %s
                RETURNING
                    id,
                    user_id,
                    source_entity_type,
                    source_entity_id,
                    candidate_entity_type,
                    candidate_entity_id,
                    feedback,
                    reason,
                    created_at,
                    updated_at
                """,
                (feedback_id, user_id),
            )
            row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="recommendation feedback not found")
    return feedback_item_from_row(row)
