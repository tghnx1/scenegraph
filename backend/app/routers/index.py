from fastapi import APIRouter

from app.routers import artist_connections, artists, feedback, graph, recommendations, search, venues, events, promoters 

router = APIRouter()

router.include_router(search.router, prefix="/search", tags=["search"])
router.include_router(artists.router, prefix="/artist", tags=["artists"])
router.include_router(venues.router, prefix="/venue", tags=["venues"])
router.include_router(events.router, prefix="/event", tags=["events"])
router.include_router(promoters.router, prefix="/promoter", tags=["promoters"])
router.include_router(artist_connections.router, prefix="/artists", tags=["artist-connections"])
router.include_router(recommendations.router, tags=["recommendations"])
router.include_router(feedback.router, tags=["feedback"])
router.include_router(graph.router, tags=["graph"])
