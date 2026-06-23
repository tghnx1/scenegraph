from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from psycopg import Connection

from app.auth import _user_id_from_jwt, get_current_user_id
from app.db import get_connection, get_db
from app.recommendation_job_events import recommendation_job_socket_hub
from app.recommendation_jobs import create_recommendation_job, get_recommendation_job
from app.recommendation_scoring import promoter_recommendation_api_limit_max_from_env
from app.schemas import (
    PromoterRecommendationResponse,
    RecommendationJobCreatedResponse,
    RecommendationJobParams,
    RecommendationJobResponse,
)


router = APIRouter()
PROMOTER_REC_API_LIMIT_MAX = promoter_recommendation_api_limit_max_from_env()


# Convert a database job row into the public API contract.
def _job_response(row: dict[str, object]) -> RecommendationJobResponse:
    """Convert a database job row into the public user-scoped API contract."""
    result_json = row["result_json"]
    return RecommendationJobResponse(
        jobId=str(row["id"]),
        jobType="artist_promoters",
        artistId=int(row["artist_id"]),
        params=RecommendationJobParams.model_validate(row["params_json"]),
        status=str(row["status"]),
        result=(
            PromoterRecommendationResponse.model_validate(result_json)
            if result_json is not None
            else None
        ),
        errorMessage=str(row["error_message"]) if row["error_message"] is not None else None,
        createdAt=row["created_at"],
        startedAt=row["started_at"],
        finishedAt=row["finished_at"],
        updatedAt=row["updated_at"],
    )


# Create a durable job and return before recommendation computation starts.
@router.post(
    "/recommendations/artists/{artist_id}/promoters/jobs",
    response_model=RecommendationJobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_artist_promoter_job(
    artist_id: int,
    params: RecommendationJobParams,
    user_id: int = Depends(get_current_user_id),
    connection: Connection = Depends(get_db),
) -> RecommendationJobCreatedResponse:
    """Create a durable recommendation job and return without running recommendations."""
    if params.limit > PROMOTER_REC_API_LIMIT_MAX:
        raise HTTPException(
            status_code=422,
            detail=f"limit must be less than or equal to {PROMOTER_REC_API_LIMIT_MAX}",
        )

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM artists WHERE id = %s", (artist_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail=f"Artist {artist_id} not found")

    row = create_recommendation_job(
        connection,
        user_id=user_id,
        artist_id=artist_id,
        params=params.model_dump(mode="json"),
    )
    return RecommendationJobCreatedResponse(jobId=str(row["id"]), status="queued")


# Return job status and result only to its authenticated owner.
@router.get(
    "/recommendations/jobs/{job_id}",
    response_model=RecommendationJobResponse,
    response_model_exclude_none=True,
)
def read_recommendation_job(
    job_id: UUID,
    user_id: int = Depends(get_current_user_id),
    connection: Connection = Depends(get_db),
) -> RecommendationJobResponse:
    """Return current job state and the result only to the owning user."""
    row = get_recommendation_job(
        connection,
        job_id=str(job_id),
        user_id=user_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Recommendation job not found")
    return _job_response(row)


# Hold the browser's user-scoped recommendation status channel open.
@router.websocket("/ws/recommendations")
async def recommendation_jobs_ws(
    websocket: WebSocket,
    token: Annotated[str | None, Query()] = None,
) -> None:
    """Authenticate a browser and keep its user-scoped job signal channel open."""
    if not token:
        await websocket.close(code=1008)
        return

    try:
        with get_connection() as connection:
            user_id = _user_id_from_jwt(token, connection)
    except HTTPException:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await recommendation_job_socket_hub.add(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await recommendation_job_socket_hub.remove(user_id, websocket)
