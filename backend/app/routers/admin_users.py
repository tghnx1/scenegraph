from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.admin import users as admin_users_service
from app.auth import require_admin
from app.db import get_connection
from app.schemas import ChangeRoleRequest

router = APIRouter()


@router.get("/users/pending")
async def list_pending_users(admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        users = admin_users_service.list_pending_users(connection)
    return {"success": True, "users": users}


@router.post("/users/{user_id}/approve")
async def approve_user(user_id: int, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        updated_user = admin_users_service.approve_user(connection, user_id=user_id, admin=admin)
    return {"success": True, "message": "User approved", "user": updated_user}


@router.post("/users/{user_id}/reject")
async def reject_user(user_id: int, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        updated_user = admin_users_service.reject_user(connection, user_id=user_id, admin=admin)
    return {"success": True, "message": "User rejected", "user": updated_user}


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(user_id: int, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        updated_user = admin_users_service.deactivate_user(connection, user_id=user_id, admin=admin)
    return {"success": True, "message": "User deactivated", "user": updated_user}


@router.post("/users/{user_id}/activate")
async def activate_user(user_id: int, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        updated_user = admin_users_service.activate_user(connection, user_id=user_id, admin=admin)
    return {"success": True, "message": "User activated", "user": updated_user}


@router.get("/activity")
async def list_activity(admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        rows = admin_users_service.list_activity(connection)
    return {"success": True, "activity": rows}


@router.get("/users")
async def list_users(admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        users = admin_users_service.list_users(connection)
    return {"success": True, "users": users}


@router.get("/activity/export", response_class=PlainTextResponse)
async def export_activity(admin: dict = Depends(require_admin)) -> str:
    with get_connection() as connection:
        rows = admin_users_service.export_activity_rows(connection)
    return admin_users_service.render_activity_export(rows)


@router.post("/users/{user_id}/role")
async def change_user_role(
    user_id: int,
    role_data: ChangeRoleRequest,
    admin: dict = Depends(require_admin),
) -> dict:
    with get_connection() as connection:
        updated_user = admin_users_service.change_user_role(
            connection,
            user_id=user_id,
            role_data=role_data,
            admin=admin,
        )
    return {"success": True, "message": "User role changed", "user": updated_user}
