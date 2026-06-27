from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import get_connection
from app.recommendations.helpers import ensure_feedback_entity_exists
from app.schemas import (
    ArtistKnownConnectionItem,
    ArtistKnownConnectionRequest,
    ArtistKnownConnectionResponse,
)


router = APIRouter()


def item_from_row(row: dict) -> ArtistKnownConnectionItem:
    return ArtistKnownConnectionItem(
        sourceArtistId=row["source_artist_id"],
        connectedArtistId=row["connected_artist_id"],
        connectedArtistName=row["connected_artist_name"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


@router.get(
    "/{artist_id}/known-artists",
    response_model=ArtistKnownConnectionResponse,
    response_model_exclude_none=True,
)
async def list_known_artists(
    artist_id: int,
) -> ArtistKnownConnectionResponse:
    with get_connection() as connection:
        ensure_feedback_entity_exists(connection, entity_type="artist", entity_id=artist_id)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    amc.source_artist_id,
                    amc.connected_artist_id,
                    a.name AS connected_artist_name,
                    amc.created_at,
                    amc.updated_at
                FROM artist_manual_connections amc
                JOIN artists a
                  ON a.id = amc.connected_artist_id
                WHERE amc.source_artist_id = %s
                ORDER BY amc.updated_at DESC, amc.connected_artist_id ASC
                """,
                (artist_id,),
            )
            rows = cursor.fetchall()

    return ArtistKnownConnectionResponse(items=[item_from_row(row) for row in rows])


@router.post(
    "/{artist_id}/known-artists",
    response_model=ArtistKnownConnectionItem,
    response_model_exclude_none=True,
)
async def upsert_known_artist(
    artist_id: int,
    request: ArtistKnownConnectionRequest,
) -> ArtistKnownConnectionItem:
    if artist_id == request.connectedArtistId:
        raise HTTPException(status_code=400, detail="source artist and connected artist must be different")

    with get_connection() as connection:
        ensure_feedback_entity_exists(connection, entity_type="artist", entity_id=artist_id)
        ensure_feedback_entity_exists(connection, entity_type="artist", entity_id=request.connectedArtistId)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO artist_manual_connections (
                    source_artist_id,
                    connected_artist_id
                )
                VALUES (%s, %s)
                ON CONFLICT (source_artist_id, connected_artist_id)
                DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP
                RETURNING
                    source_artist_id,
                    connected_artist_id,
                    created_at,
                    updated_at
                """,
                (artist_id, request.connectedArtistId),
            )
            row = cursor.fetchone()
            cursor.execute(
                "SELECT name FROM artists WHERE id = %s",
                (request.connectedArtistId,),
            )
            artist_row = cursor.fetchone()

    row["connected_artist_name"] = artist_row["name"] if artist_row else ""
    return item_from_row(row)


@router.delete(
    "/{artist_id}/known-artists/{connected_artist_id}",
    response_model=ArtistKnownConnectionItem,
    response_model_exclude_none=True,
)
async def delete_known_artist(
    artist_id: int,
    connected_artist_id: int,
) -> ArtistKnownConnectionItem:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM artist_manual_connections
                WHERE source_artist_id = %s
                  AND connected_artist_id = %s
                RETURNING
                    source_artist_id,
                    connected_artist_id,
                    created_at,
                    updated_at
                """,
                (artist_id, connected_artist_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="manual artist connection not found")

            cursor.execute(
                "SELECT name FROM artists WHERE id = %s",
                (connected_artist_id,),
            )
            artist_row = cursor.fetchone()

    row["connected_artist_name"] = artist_row["name"] if artist_row else ""
    return item_from_row(row)
