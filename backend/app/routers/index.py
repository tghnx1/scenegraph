from fastapi import APIRouter

from app.routers import artists, feedback, graph, recommendations, search, venues, events, promoters, genres, graph_ego 

router = APIRouter()

router.include_router(search.router, prefix="/search", tags=["search"])
router.include_router(artists.router, prefix="/artists", tags=["artists"])
router.include_router(venues.router, prefix="/venues", tags=["venues"])
router.include_router(events.router, prefix="/events", tags=["events"])
router.include_router(promoters.router, prefix="/promoters", tags=["promoters"])
router.include_router(genres.router, prefix="/genres", tags=["genres"])
router.include_router(graph_ego.router, prefix="/graph", tags=["graph"])

router.include_router(recommendations.router, tags=["recommendations"])
router.include_router(feedback.router, tags=["feedback"])
router.include_router(graph.router, tags=["graph"])
