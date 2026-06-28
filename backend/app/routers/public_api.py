from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import check_rate_limit, require_public_api_key
from app.db import get_connection
from app.schemas import Venue, VenuesResponse

router = APIRouter()


@router.get("/venues", response_model=VenuesResponse)
async def list_venues() -> VenuesResponse:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    COALESCE(area_name, country_code, '') AS district,
                    COALESCE(address, content_url, '') AS scene_focus
                FROM venues
                ORDER BY id ASC
                """
            )
            venues = cursor.fetchall()
    return VenuesResponse(venues=[Venue(**venue) for venue in venues])


# @router.get("/public/venues")
# async def public_venues(_: None = Depends(require_public_api_key), limit: int = 20, offset: int = 0) -> dict:
#     check_rate_limit("public:venues", max_attempts=100, window_seconds=60)
#     limit = min(max(limit, 1), 100)
#     offset = max(offset, 0)
#     with get_connection() as connection:
#         with connection.cursor() as cursor:
#             cursor.execute(
#                 """
#                 SELECT id, name
#                 FROM venues
#                 ORDER BY name ASC
#                 LIMIT %s OFFSET %s
#                 """,
#                 (limit, offset),
#             )
#             rows = cursor.fetchall()
#     return {"success": True, "limit": limit, "offset": offset, "venues": rows}


@router.get("/public/artists")
async def public_artists(_: None = Depends(require_public_api_key), limit: int = 20, offset: int = 0) -> dict:
    check_rate_limit("public:artists", max_attempts=100, window_seconds=60)
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name
                FROM artists
                ORDER BY name ASC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()
    return {"success": True, "limit": limit, "offset": offset, "artists": rows}


@router.get("/public/events")
async def public_events(_: None = Depends(require_public_api_key), limit: int = 20, offset: int = 0) -> dict:
    check_rate_limit("public:events", max_attempts=100, window_seconds=60)
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name
                FROM events
                ORDER BY name ASC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()
    return {"success": True, "limit": limit, "offset": offset, "events": rows}


@router.get("/public/promoters")
async def public_promoters(_: None = Depends(require_public_api_key), limit: int = 20, offset: int = 0) -> dict:
    check_rate_limit("public:promoters", max_attempts=100, window_seconds=60)
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name
                FROM promoters
                ORDER BY name ASC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()
    return {"success": True, "limit": limit, "offset": offset, "promoters": rows}


# @router.get("/public/genres")
# async def get_public_genres(_: None = Depends(require_public_api_key), limit: int = 20, offset: int = 0) -> dict:
#     check_rate_limit("public:genres", max_attempts=100, window_seconds=60)
#     limit = min(max(limit, 1), 100)
#     offset = max(offset, 0)
#     with get_connection() as connection:
#         with connection.cursor() as cursor:
#             cursor.execute(
#                 """
#                 SELECT id, name
#                 FROM genres
#                 ORDER BY name ASC
#                 LIMIT %s OFFSET %s
#                 """,
#                 (limit, offset),
#             )
#             rows = cursor.fetchall()
#     return {"success": True, "limit": limit, "offset": offset, "genres": rows}
