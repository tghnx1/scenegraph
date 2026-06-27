from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user, log_activity, require_admin
from app.db import get_connection
from app.schemas import ArtistClaimRequest

router = APIRouter()


@router.post("/artists/{artist_id}/claim")
async def claim_artist_profile(
    artist_id: int,
    claim_data: ArtistClaimRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "artist":
        raise HTTPException(status_code=403, detail="Only artists can claim profiles")

    reason = claim_data.reason.strip()
    if len(reason) < 6:
        raise HTTPException(status_code=400, detail="Reason must be at least 6 characters")
    if len(reason) > 80:
        raise HTTPException(status_code=400, detail="Reason must be more concise")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM artists WHERE id = %s", (artist_id,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Artist not found")

            cursor.execute(
                """
                SELECT id, username
                FROM users
                WHERE artist_id = %s
                    AND id != %s
                LIMIT 1
                """,
                (artist_id, current_user["id"]),
            )
            assigned_user = cursor.fetchone()
            if assigned_user is not None:
                raise HTTPException(
                    status_code=409,
                    detail="This artist profile has already been assigned to another user.",
                )

            cursor.execute(
                """
                SELECT id, status
                FROM artist_claims
                WHERE user_id = %s
                AND artist_id = %s
                AND status = 'pending'
                """,
                (current_user["id"], artist_id),
            )
            existing_claim = cursor.fetchone()
            if existing_claim is not None:
                raise HTTPException(
                    status_code=409,
                    detail="You already have a pending claim for this artist profile.",
                )

            cursor.execute(
                """
                INSERT INTO artist_claims (user_id, artist_id, reason)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (current_user["id"], artist_id, reason),
            )
            claim = cursor.fetchone()

        log_activity(connection, current_user["id"], current_user["username"], "artist claim submitted", f"artist {artist_id}")
        connection.commit()

    return {"success": True, "message": "Claim submitted", "claim_id": claim["id"]}


@router.get("/admin/artist-claims")
async def get_artist_claims(admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    artist_claims.id,
                    artist_claims.status,
                    artist_claims.reason,
                    artist_claims.created_at,
                    users.username,
                    users.email,
                    artists.name AS artist_name,
                    artist_claims.artist_id
                FROM artist_claims
                JOIN users ON users.id = artist_claims.user_id
                JOIN artists ON artists.id = artist_claims.artist_id
                ORDER BY artist_claims.created_at DESC
                """
            )
            claims = cursor.fetchall()
    return {"success": True, "claims": claims}


@router.post("/admin/artist-claims/{claim_id}/approve")
async def approve_artist_claim(claim_id: int, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    artist_claims.id,
                    artist_claims.user_id,
                    artist_claims.artist_id,
                    artist_claims.status,
                    users.username,
                    artists.name AS artist_name
                FROM artist_claims
                JOIN users ON users.id = artist_claims.user_id
                JOIN artists ON artists.id = artist_claims.artist_id
                WHERE artist_claims.id = %s
                """,
                (claim_id,),
            )
            claim = cursor.fetchone()
            if claim is None:
                raise HTTPException(status_code=404, detail="Claim not found")
            if claim["status"] != "pending":
                raise HTTPException(status_code=400, detail="Claim already decided")

            cursor.execute(
                """
                UPDATE users
                SET artist_id = %s
                WHERE id = %s
                """,
                (claim["artist_id"], claim["user_id"]),
            )
            cursor.execute(
                """
                UPDATE artist_claims
                SET status = 'approved',
                    decided_at = CURRENT_TIMESTAMP,
                    decided_by = %s
                WHERE id = %s
                """,
                (admin["id"], claim_id),
            )

        log_activity(connection, admin["id"], admin["username"], "artist claim approved", f"{claim['username']} → {claim['artist_name']}")
        connection.commit()
    return {"success": True, "message": "Artist claim approved"}


@router.post("/admin/artist-claims/{claim_id}/reject")
async def reject_artist_claim(claim_id: int, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    artist_claims.id,
                    artist_claims.user_id,
                    artist_claims.artist_id,
                    artist_claims.status,
                    users.username,
                    artists.name AS artist_name
                FROM artist_claims
                JOIN users ON users.id = artist_claims.user_id
                JOIN artists ON artists.id = artist_claims.artist_id
                WHERE artist_claims.id = %s
                """,
                (claim_id,),
            )
            claim = cursor.fetchone()
            if claim is None:
                raise HTTPException(status_code=404, detail="Claim not found")
            if claim["status"] != "pending":
                raise HTTPException(status_code=400, detail="Claim already decided")

            cursor.execute(
                """
                UPDATE artist_claims
                SET status = 'rejected',
                    decided_at = CURRENT_TIMESTAMP,
                    decided_by = %s
                WHERE id = %s
                  AND status = 'pending'
                RETURNING id
                """,
                (admin["id"], claim_id),
            )
            updated_claim = cursor.fetchone()
            if updated_claim is None:
                raise HTTPException(status_code=400, detail="Claim already decided")

        log_activity(connection, admin["id"], admin["username"], "artist claim rejected", f"{claim['username']} → {claim['artist_name']}")
        connection.commit()
    return {"success": True, "message": "Artist claim rejected"}
