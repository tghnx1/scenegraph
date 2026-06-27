from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from app.auth import log_activity, require_admin
from app.db import get_connection
from app.schemas import ChangeRoleRequest

router = APIRouter()


@router.get("/users/pending")
async def list_pending_users(admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, email, role, status, created_at
                FROM users
                WHERE status = 'pending'
                ORDER BY created_at ASC
                """
            )
            users = cursor.fetchall()
    return {"success": True, "users": users}


@router.post("/users/{user_id}/approve")
async def approve_user(user_id: int, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET status = 'approved'
                WHERE id = %s
                RETURNING id, username, email, role, status
                """,
                (user_id,),
            )
            updated_user = cursor.fetchone()
        if updated_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        log_activity(connection, admin["id"], admin["username"], "user approved", updated_user["username"])
        connection.commit()
    return {"success": True, "message": "User approved", "user": updated_user}


@router.post("/users/{user_id}/reject")
async def reject_user(user_id: int, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
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
        if updated_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        log_activity(connection, admin["id"], admin["username"], "user registration rejected", updated_user["username"])
        connection.commit()
    return {"success": True, "message": "User rejected", "user": updated_user}


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(user_id: int, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET status = 'deactivated'
                WHERE id = %s
                RETURNING id, username, email, role, status
                """,
                (user_id,),
            )
            updated_user = cursor.fetchone()
            if updated_user is None:
                raise HTTPException(status_code=404, detail="User not found")
            log_activity(connection, updated_user["id"], updated_user["username"], "deactivation", f"Deactivated by {admin['username']}")
            log_activity(connection, admin["id"], admin["username"], "user deactivated", updated_user["username"])
            connection.commit()
    return {"success": True, "message": "User deactivated", "user": updated_user}


@router.post("/users/{user_id}/activate")
async def activate_user(user_id: int, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET status = 'approved'
                WHERE id = %s
                RETURNING id, username, email, role, status
                """,
                (user_id,),
            )
            updated_user = cursor.fetchone()
            if updated_user is None:
                raise HTTPException(status_code=404, detail="User not found")
            log_activity(connection, updated_user["id"], updated_user["username"], "activation", f"Activated by {admin['username']}")
            log_activity(connection, admin["id"], admin["username"], "user activated", updated_user["username"])
            connection.commit()
    return {"success": True, "message": "User activated", "user": updated_user}


@router.get("/activity")
async def list_activity(admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, event_type, target, created_at
                FROM activity_log
                ORDER BY created_at DESC
                LIMIT 20
                """
            )
            rows = cursor.fetchall()
    return {"success": True, "activity": rows}


@router.get("/users")
async def list_users(admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, email, role, status, created_at
                FROM users
                ORDER BY created_at DESC
                """
            )
            users = cursor.fetchall()
    return {"success": True, "users": users}


@router.get("/activity/export", response_class=PlainTextResponse)
async def export_activity(admin: dict = Depends(require_admin)) -> str:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, event_type, target, created_at
                FROM activity_log
                ORDER BY created_at DESC
                """
            )
            rows = cursor.fetchall()
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


@router.post("/users/{user_id}/role")
async def change_user_role(
    user_id: int,
    role_data: ChangeRoleRequest,
    admin: dict = Depends(require_admin),
) -> dict:
    if role_data.role not in {"artist", "agent"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    with get_connection() as connection:
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
    return {"success": True, "message": "User role changed", "user": updated_user}
