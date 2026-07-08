from fastapi import APIRouter

from app.routers import (
    admin_users,
    artist_connections,
    artists,
    composition,
    dashboard_ws,
    events,
    feedback,
    genres,
    graph,
    graph_ego,
    imports,
    metrics,
    promoters,
    public_api,
    recommendation_jobs,
    recommendations,
    search,
    session,
    venues,
)

router = APIRouter()

router.include_router(session.router, tags=["auth"])
router.include_router(search.router, prefix="/search", tags=["search"])
router.include_router(artists.router, prefix="/artist", tags=["artists"])
router.include_router(venues.router, prefix="/venue", tags=["venues"])
router.include_router(events.router, prefix="/event", tags=["events"])
router.include_router(promoters.router, prefix="/promoter", tags=["promoters"])
router.include_router(artist_connections.router, prefix="/artists", tags=["artist-connections"])
router.include_router(recommendations.router, tags=["recommendations"])
router.include_router(feedback.router, tags=["feedback"])
router.include_router(graph.router, tags=["graph"])
router.include_router(graph_ego.router, prefix="/graph", tags=["graph"])
router.include_router(genres.router, prefix="/genres", tags=["genres"])
router.include_router(public_api.router, tags=["public-api"])
router.include_router(admin_users.router, prefix="/admin", tags=["admin"])
router.include_router(composition.router, prefix="/admin", tags=["admin"])
router.include_router(metrics.router, prefix="/admin", tags=["admin"])
router.include_router(dashboard_ws.router, prefix="/ws", tags=["websocket"])
router.include_router(recommendation_jobs.router, tags=["recommendation-jobs"])
router.include_router(imports.router, prefix="/admin", tags=["admin"])
