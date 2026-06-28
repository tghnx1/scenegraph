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
            SELECT id, username, email, role, status, created_at
            FROM users
            WHERE status = 'pending'
            ORDER BY created_at ASC
            """
        )
        return cursor.fetchall()


def approve_user(connection: Connection, *, user_id: int, admin: dict) -> dict:
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
    return updated_user


def reject_user(connection: Connection, *, user_id: int, admin: dict) -> dict:
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
    return updated_user


def deactivate_user(connection: Connection, *, user_id: int, admin: dict) -> dict:
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
                    stauts_code=400,
                    detail="At least one approved admin must remain active.",
                )
        
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
    return updated_user


def activate_user(connection: Connection, *, user_id: int, admin: dict) -> dict:
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
            SELECT id, username, email, role, status, created_at
            FROM users
            ORDER BY created_at DESC
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
