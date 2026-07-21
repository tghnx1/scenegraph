from __future__ import annotations

from fastapi import HTTPException
from psycopg import Connection

from app.auth import log_activity
from app.schemas import ChangeRoleRequest

import os

BOOTSTRAP_ADMIN_USERNAME = os.getenv("BOOTSTRAP_ADMIN_USERNAME")


def list_pending_users(connection: Connection) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                users.id,
                users.username,
                users.email,
                users.role,
                users.status,
                users.created_at,
                artist_claims.id AS artist_claim_id,
                artist_claims.artist_id,
                artist_claims.instagram_url AS artist_instagram_url,
                artists.name AS artist_name,
                artists.content_url AS artist_content_url,
                artists.ra_artist_id AS artist_ra_artist_id,
                CASE
                    WHEN artists.ra_artist_id IS NULL THEN 'user_created'
                    ELSE 'resident_advisor'
                END AS artist_source
            FROM users
            LEFT JOIN artist_claims
                ON artist_claims.user_id = users.id
               AND artist_claims.status = 'pending'
            LEFT JOIN artists
                ON artists.id = artist_claims.artist_id
            WHERE users.status = 'pending'
            ORDER BY users.created_at ASC
            """
        )
        return cursor.fetchall()


def approve_user(connection: Connection, *, user_id: int, admin: dict) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                users.id,
                users.username,
                users.email,
                users.role,
                users.status,
                artist_claims.id AS artist_claim_id,
                artist_claims.artist_id,
                artist_claims.instagram_url AS artist_instagram_url,
                artists.name AS artist_name,
                artists.content_url AS artist_content_url,
                artists.ra_artist_id AS artist_ra_artist_id,
                CASE
                    WHEN artists.ra_artist_id IS NULL THEN 'user_created'
                    ELSE 'resident_advisor'
                END AS artist_source
            FROM users
            LEFT JOIN artist_claims
                ON artist_claims.user_id = users.id
               AND artist_claims.status = 'pending'
            LEFT JOIN artists
                ON artists.id = artist_claims.artist_id
            WHERE users.id = %s
            FOR UPDATE OF users
            """,
            (user_id,),
        )
        target_user = cursor.fetchone()
        if target_user is None:
            raise HTTPException(status_code=404, detail="User not found")

        if target_user["role"] == "artist" and target_user["artist_id"] is not None:
            cursor.execute(
                """
                SELECT id, username
                FROM users
                WHERE artist_id = %s
                  AND id != %s
                  AND status IN ('pending', 'approved')
                LIMIT 1
                """,
                (target_user["artist_id"], user_id),
            )
            assigned_user = cursor.fetchone()
            if assigned_user is not None:
                raise HTTPException(status_code=409, detail="Artist profile is already assigned")

        cursor.execute(
            """
            UPDATE users
            SET status = 'approved',
                artist_id = COALESCE(%s, artist_id)
            WHERE id = %s
            RETURNING id, username, email, role, status, artist_id
            """,
            (target_user["artist_id"], user_id),
        )
        updated_user = cursor.fetchone()

        if target_user["artist_claim_id"] is not None:
            cursor.execute(
                """
                UPDATE artist_claims
                SET status = 'approved',
                    decided_at = CURRENT_TIMESTAMP,
                    decided_by = %s
                WHERE id = %s
                """,
                (admin["id"], target_user["artist_claim_id"]),
            )

    log_activity(connection, admin["id"], admin["username"], "user approved", updated_user["username"], commit=False)
    if target_user["artist_name"] is not None:
        log_activity(
            connection,
            admin["id"],
            admin["username"],
            "artist claim approved",
            f"{updated_user['username']} → {target_user['artist_name']}",
            commit=False,
        )
    connection.commit()
    return updated_user


def _delete_safe_user_created_artist(connection: Connection, artist_id: int) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                a.id,
                a.ra_artist_id,
                EXISTS(SELECT 1 FROM event_artists ea WHERE ea.artist_id = a.id) AS has_event_artists,
                EXISTS(SELECT 1 FROM recommendation_jobs rj WHERE rj.artist_id = a.id) AS has_recommendation_jobs,
                EXISTS(SELECT 1 FROM artist_extracted_tags aet WHERE aet.artist_id = a.id) AS has_artist_tags,
                EXISTS(SELECT 1 FROM artist_tag_extraction_runs atr WHERE atr.artist_id = a.id) AS has_artist_tag_runs,
                EXISTS(
                    SELECT 1
                    FROM artist_manual_connections amc
                    WHERE amc.source_artist_id = a.id OR amc.connected_artist_id = a.id
                ) AS has_manual_connections,
                EXISTS(
                    SELECT 1
                    FROM users u
                    WHERE u.artist_id = a.id
                      AND u.status IN ('pending', 'approved')
                ) AS has_assigned_users,
                EXISTS(
                    SELECT 1
                    FROM artist_claims ac
                    WHERE ac.artist_id = a.id
                      AND ac.status IN ('pending', 'approved')
                ) AS has_active_claims
            FROM artists a
            WHERE a.id = %s
            """,
            (artist_id,),
        )
        artist_row = cursor.fetchone()
        if artist_row is None:
            return False

        if (
            artist_row["ra_artist_id"] is not None
            or artist_row["has_event_artists"]
            or artist_row["has_recommendation_jobs"]
            or artist_row["has_artist_tags"]
            or artist_row["has_artist_tag_runs"]
            or artist_row["has_manual_connections"]
            or artist_row["has_assigned_users"]
            or artist_row["has_active_claims"]
        ):
            return False

        cursor.execute(
            """
            DELETE FROM artist_claims
            WHERE artist_id = %s
              AND status = 'rejected'
            """,
            (artist_id,),
        )
        cursor.execute(
            """
            DELETE FROM artists
            WHERE id = %s
            """,
            (artist_id,),
        )
        return cursor.rowcount > 0


def reject_user(connection: Connection, *, user_id: int, admin: dict) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                users.id,
                users.username,
                users.email,
                users.role,
                users.status,
                artist_claims.id AS artist_claim_id,
                artist_claims.artist_id,
                artist_claims.instagram_url AS artist_instagram_url,
                artists.name AS artist_name,
                artists.content_url AS artist_content_url,
                artists.ra_artist_id AS artist_ra_artist_id,
                CASE
                    WHEN artists.ra_artist_id IS NULL THEN 'user_created'
                    ELSE 'resident_advisor'
                END AS artist_source
            FROM users
            LEFT JOIN artist_claims
                ON artist_claims.user_id = users.id
               AND artist_claims.status = 'pending'
            LEFT JOIN artists
                ON artists.id = artist_claims.artist_id
            WHERE users.id = %s
            FOR UPDATE OF users
            """,
            (user_id,),
        )
        target_user = cursor.fetchone()

        if target_user is None:
            raise HTTPException(status_code=404, detail="User not found")

        cursor.execute(
            """
            UPDATE users
            SET status = 'rejected'
            WHERE id = %s
            RETURNING id, username, email, role, status
            """,
            (user_id,),
        )
        updated_user = cursor.fetchone()

        if target_user["artist_claim_id"] is not None:
            cursor.execute(
                """
                UPDATE artist_claims
                SET status = 'rejected',
                    decided_at = CURRENT_TIMESTAMP,
                    decided_by = %s
                WHERE id = %s
                """,
                (admin["id"], target_user["artist_claim_id"]),
            )

        if target_user["artist_id"] is not None and target_user["artist_ra_artist_id"] is None:
            _delete_safe_user_created_artist(connection, int(target_user["artist_id"]))

    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    log_activity(
        connection,
        admin["id"],
        admin["username"],
        "user registration rejected",
        updated_user["username"],
        commit=False,
    )
    connection.commit()
    return updated_user


def deactivate_user(connection: Connection, *, user_id: int, admin: dict) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, role, status, artist_id
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        target_user = cursor.fetchone()

        if target_user is None:
            raise HTTPException(status_code=404, detail="User not found")

        if target_user["id"] == admin["id"]:
            raise HTTPException(
                status_code=400,
                detail="You cannot deactivate your own account.",
            )

        if target_user["username"] == BOOTSTRAP_ADMIN_USERNAME:
            raise HTTPException(
                status_code=400,
                detail="The bootstrap admin cannot be deactivated.",
            )

        if target_user["role"] == "admin":
            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE role = 'admin'
                    AND status = 'approved'
                """
            )
            approved_admins = cursor.fetchall()

            if len(approved_admins) <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="At least one approved admin must remain active.",
                )

        cursor.execute(
            """
            UPDATE users
            SET status = 'deactivated'
            WHERE id = %s
            RETURNING id, username, email, role, status, artist_id
            """,
            (user_id,),
        )
        updated_user = cursor.fetchone()
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    log_activity(connection, updated_user["id"], updated_user["username"], "deactivation", f"Deactivated by {admin['username']}")
    log_activity(connection, admin["id"], admin["username"], "user deactivated", updated_user["username"])
    connection.commit()
    return updated_user


def activate_user(connection: Connection, *, user_id: int, admin: dict) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, role, status
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        target_user = cursor.fetchone()
        if target_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if target_user["status"] != "deactivated":
            raise HTTPException(status_code=400, detail="Only deactivated users can be activated")
        cursor.execute(
            """
            UPDATE users
            SET status = 'approved'
            WHERE id = %s
            RETURNING id, username, email, role, status, artist_id
            """,
            (user_id,),
        )
        updated_user = cursor.fetchone()
        if updated_user is None:
            raise HTTPException(status_code=404, detail="User not found")
    log_activity(connection, updated_user["id"], updated_user["username"], "activation", f"Activated by {admin['username']}")
    log_activity(connection, admin["id"], admin["username"], "user activated", updated_user["username"])
    connection.commit()
    return updated_user


def list_activity(connection: Connection) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, event_type, target, created_at
            FROM activity_log
            ORDER BY created_at DESC
            LIMIT 20
            """
        )
        return cursor.fetchall()


def list_users(connection: Connection) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                users.id,
                users.username,
                users.email,
                users.role,
                users.status,
                users.created_at,
                artists.name AS artist_name,
                artists.content_url AS artist_content_url,
                artists.ra_artist_id AS artist_ra_artist_id,
                artist_claims.instagram_url AS artist_instagram_url,
                CASE
                    WHEN artists.id IS NULL THEN NULL
                    WHEN artists.ra_artist_id IS NULL THEN 'user_created'
                    ELSE 'resident_advisor'
                END AS artist_source
            FROM users
            LEFT JOIN artists
                ON artists.id = users.artist_id
            LEFT JOIN artist_claims
                ON artist_claims.user_id = users.id
               AND artist_claims.artist_id = users.artist_id
               AND artist_claims.status = 'approved'
            ORDER BY users.created_at DESC
            """
        )
        return cursor.fetchall()


def export_activity_rows(connection: Connection) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, event_type, target, created_at
            FROM activity_log
            ORDER BY created_at DESC
            """
        )
        return cursor.fetchall()


def render_activity_export(rows: list[dict]) -> str:
    lines = [
        f"{'id':<4}| {'username':<25}| {'event_type':<28}| {'target':<30}| {'created_at'}",
        f"{'-' * 4}+{'-' * 26}+{'-' * 29}+{'-' * 31}+{'-' * 30}",
    ]
    for row in rows:
        lines.append(
            f"{str(row['id']):<4}| "
            f"{(row['username'] or ''):<25}| "
            f"{row['event_type']:<28}| "
            f"{(row['target'] or ''):<30}| "
            f"{row['created_at']}"
        )
    return "\n".join(lines)


def change_user_role(connection: Connection, *, user_id: int, role_data: ChangeRoleRequest, admin: dict) -> dict:
    if role_data.role not in {"artist", "agent"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE users
            SET role = %s
            WHERE id = %s
                AND role != 'admin'
            RETURNING id, username, email, role, status
            """,
            (role_data.role, user_id),
        )
        updated_user = cursor.fetchone()
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found or cannot change admin role")
    log_activity(connection, admin["id"], admin["username"], "user role changed", f"{updated_user['username']} -> {updated_user['role']}")
    connection.commit()
    return updated_user
