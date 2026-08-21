from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from app.auth import _user_id_from_jwt, get_current_user, require_artist_access
from app.db import get_connection
from app.recommendations.job_events import recommendation_job_socket_hub
from app.recommendations.jobs import (
    create_recommendation_job,
    get_default_artist_promoter_recommendation_state,
    get_recommendation_job,
)
from app.recommendations.scoring import promoter_recommendation_api_limit_max_from_config
from app.schemas import (
    GraphLink,
    GraphResponse,
    PromoterRecommendationResponse,
    RecommendationJobCreatedResponse,
    RecommendationJobParams,
    RecommendationJobResponse,
    RecommendationJobStateResponse,
)


router = APIRouter()
PROMOTER_REC_API_LIMIT_MAX = promoter_recommendation_api_limit_max_from_config()

# Slice the stored recommendation payload for client-side pagination.
def _page_promoter_recommendation_response(
    response: PromoterRecommendationResponse,
    *,
    recommendations_offset: int = 0,
    recommendations_limit: int | None = None,
) -> PromoterRecommendationResponse:
    """Return a page view over the stored recommendation payload."""
    total_recommendations = len(response.recommendations)
    page_offset = max(recommendations_offset, 0)
    page_end = total_recommendations

    if recommendations_limit is None:
        page_limit = total_recommendations
        page_recommendations = list(response.recommendations)
        page_offset = 0
    else:
        page_limit = recommendations_limit
        page_offset = min(page_offset, total_recommendations)
        page_end = min(page_offset + page_limit, total_recommendations)
        page_recommendations = list(response.recommendations[page_offset:page_end])

    page_recommendation_ids = {recommendation.id for recommendation in page_recommendations}
    cumulative_recommendation_ids = {recommendation.id for recommendation in response.recommendations[:page_end]}

    def _filter_page(items: list) -> list:
        return [item for item in items if item.id in page_recommendation_ids]

    def _filter_graph(graph: GraphResponse) -> GraphResponse:
        if not cumulative_recommendation_ids:
            return graph.model_copy(update={"nodes": [], "links": []})

        selected_promoter_node_ids = {f"promoter-{recommendation_id}" for recommendation_id in cumulative_recommendation_ids}
        source_artist_node_id = f"artist-{response.entityId}"
        graph_node_ids = set(selected_promoter_node_ids)
        graph_node_ids.update(
            node_id
            for promoter_id in selected_promoter_node_ids
            for node_id in (
                graph.preferredPathNodeIds.get(promoter_id, [])
                + graph.fallbackPathNodeIds.get(promoter_id, [])
            )
        )
        if any(node.id == source_artist_node_id for node in graph.nodes):
            graph_node_ids.add(source_artist_node_id)

        graph_link_keys = {
            link_key
            for promoter_id in selected_promoter_node_ids
            for link_key in (
                graph.preferredPathLinkKeys.get(promoter_id, [])
                + graph.fallbackPathLinkKeys.get(promoter_id, [])
            )
        }
        filtered_links = [
            link
            for link in graph.links
            if f"{min(link.source, link.target)}|{max(link.source, link.target)}" in graph_link_keys
        ]
        linked_promoter_node_ids = {
            node_id
            for link in filtered_links
            for node_id in (link.source, link.target)
            if node_id in selected_promoter_node_ids
        }
        synthesized_links = [
            GraphLink(
                source=source_artist_node_id,
                target=promoter_node_id,
                relationship="fallback_recommendation",
                weight=1,
                evidenceType="fallback_recommendation",
                style="dashed",
                strength=0.12,
            )
            for promoter_node_id in sorted(selected_promoter_node_ids)
            if promoter_node_id not in linked_promoter_node_ids
            and source_artist_node_id in graph_node_ids
            and promoter_node_id in graph_node_ids
        ]

        return graph.model_copy(
            update={
                "nodes": [node for node in graph.nodes if node.id in graph_node_ids],
                "links": filtered_links + synthesized_links,
                "preferredPathNodeIds": {
                    promoter_id: node_ids
                    for promoter_id, node_ids in graph.preferredPathNodeIds.items()
                    if promoter_id in selected_promoter_node_ids
                },
                "preferredPathLinkKeys": {
                    promoter_id: link_keys
                    for promoter_id, link_keys in graph.preferredPathLinkKeys.items()
                    if promoter_id in selected_promoter_node_ids
                },
                "preferredPathPromoterIdsByNodeId": {
                    node_id: promoter_ids
                    for node_id, promoter_ids in graph.preferredPathPromoterIdsByNodeId.items()
                    if selected_promoter_node_ids.intersection(promoter_ids)
                },
                "preferredPathPromoterIdsByLinkKey": {
                    link_key: promoter_ids
                    for link_key, promoter_ids in graph.preferredPathPromoterIdsByLinkKey.items()
                    if selected_promoter_node_ids.intersection(promoter_ids)
                },
                "fallbackPathNodeIds": {
                    promoter_id: node_ids
                    for promoter_id, node_ids in graph.fallbackPathNodeIds.items()
                    if promoter_id in selected_promoter_node_ids
                },
                "fallbackPathLinkKeys": {
                    promoter_id: link_keys
                    for promoter_id, link_keys in graph.fallbackPathLinkKeys.items()
                    if promoter_id in selected_promoter_node_ids
                },
                "fallbackPathPromoterIdsByNodeId": {
                    node_id: promoter_ids
                    for node_id, promoter_ids in graph.fallbackPathPromoterIdsByNodeId.items()
                    if selected_promoter_node_ids.intersection(promoter_ids)
                },
                "fallbackPathPromoterIdsByLinkKey": {
                    link_key: promoter_ids
                    for link_key, promoter_ids in graph.fallbackPathPromoterIdsByLinkKey.items()
                    if selected_promoter_node_ids.intersection(promoter_ids)
                },
            },
        )

    return response.model_copy(
        update={
            "recommendations": page_recommendations,
            "recommendationsTotal": total_recommendations,
            "recommendationsOffset": page_offset,
            "recommendationsLimit": page_limit,
            "recommendationsHasMore": page_offset + len(page_recommendations) < total_recommendations,
            "largeRecommendations": _filter_page(response.largeRecommendations),
            "mediumRecommendations": _filter_page(response.mediumRecommendations),
            "smallRecommendations": _filter_page(response.smallRecommendations),
            "warmRecommendations": _filter_page(response.warmRecommendations),
            "discoveryRecommendations": _filter_page(response.discoveryRecommendations),
            "graph": _filter_graph(response.graph),
            "analyticsGraph": _filter_graph(response.analyticsGraph) if response.analyticsGraph is not None else None,
        },
    )


# Convert a database job row into the public API contract.
def _job_response(
    row: dict[str, object],
    *,
    recommendations_offset: int = 0,
    recommendations_limit: int | None = None,
) -> RecommendationJobResponse:
    """Convert a database job row into the public user-scoped API contract."""
    result_json = row["result_json"]
    return RecommendationJobResponse(
        jobId=str(row["id"]),
        jobType="artist_promoters",
        artistId=int(row["artist_id"]),
        params=RecommendationJobParams.model_validate(row["params_json"]),
        status=str(row["status"]),
        result=(
            _page_promoter_recommendation_response(
                PromoterRecommendationResponse.model_validate(result_json),
                recommendations_offset=recommendations_offset,
                recommendations_limit=recommendations_limit,
            )
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
    current_user: dict = Depends(get_current_user),
) -> RecommendationJobCreatedResponse:
    """Create a durable recommendation job and return without running recommendations."""
    require_artist_access(current_user, artist_id)
    if params.limit > PROMOTER_REC_API_LIMIT_MAX:
        raise HTTPException(
            status_code=422,
            detail=f"limit must be less than or equal to {PROMOTER_REC_API_LIMIT_MAX}",
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM artists WHERE id = %s", (artist_id,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail=f"Artist {artist_id} not found")

        row = create_recommendation_job(
            connection,
            user_id=int(current_user["id"]),
            artist_id=artist_id,
            params=params.model_dump(mode="json"),
        )
    return RecommendationJobCreatedResponse(jobId=str(row["id"]), status=str(row["status"]))


# Return job status and result only to its authenticated owner.
@router.get(
    "/recommendations/jobs/{job_id}",
    response_model=RecommendationJobResponse,
    response_model_exclude_none=True,
)
def read_recommendation_job(
    job_id: UUID,
    recommendations_offset: Annotated[int, Query(ge=0)] = 0,
    recommendations_limit: Annotated[int | None, Query(ge=1, le=PROMOTER_REC_API_LIMIT_MAX)] = None,
    current_user: dict = Depends(get_current_user),
) -> RecommendationJobResponse:
    """Return current job state and the result only to the owning user."""
    with get_connection() as connection:
        row = get_recommendation_job(
            connection,
            job_id=str(job_id),
            user_id=int(current_user["id"]),
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Recommendation job not found")
    return _job_response(
        row,
        recommendations_offset=recommendations_offset,
        recommendations_limit=recommendations_limit,
    )


# Read the current durable default recommendation state for an artist.
@router.get(
    "/recommendations/artists/{artist_id}/promoters/jobs/state",
    response_model=RecommendationJobStateResponse,
    response_model_exclude_none=True,
)
def read_artist_promoter_job_state(
    artist_id: int,
    current_user: dict = Depends(get_current_user),
) -> RecommendationJobStateResponse:
    """Return the newest completed job and current active job for the default UI params."""
    require_artist_access(current_user, artist_id)
    with get_connection() as connection:
        latest_completed_row, active_row = get_default_artist_promoter_recommendation_state(
            connection,
            user_id=int(current_user["id"]),
            artist_id=artist_id,
        )
    return RecommendationJobStateResponse(
        latestCompletedJob=(
            _job_response(latest_completed_row)
            if latest_completed_row is not None
            else None
        ),
        activeJob=(
            _job_response(active_row)
            if active_row is not None
            else None
        ),
    )


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
