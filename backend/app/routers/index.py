from fastapi import APIRouter
from app.routers import search, artists

router = APIRouter()

router.include_router(search.router,    prefix="/search",    tags=["search"])
router.include_router(artists.router,   prefix="/artists",   tags=["artists"])