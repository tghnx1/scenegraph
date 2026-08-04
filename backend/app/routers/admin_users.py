from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.admin.settings import (
    AUTO_APPROVE_PENDING_USERS_SETTING,
    get_boolean_setting,
    set_boolean_setting,
    SHOW_GRAPH_TAB_SETTING,
)
from app.admin import users as admin_users_service
from app.auth import require_admin
from app.db import get_connection
from app.auth import log_activity
from app.schemas import (
    ChangeRoleRequest,
    RegistrationSettingsResponse,
    UiSettingsResponse,
    UpdateRegistrationSettingsRequest,
    UpdateUiSettingsRequest,
)

router = APIRouter()


@router.get("/settings/registration", response_model=RegistrationSettingsResponse)
async def get_registration_settings(admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        auto_approve_pending_users = get_boolean_setting(
            connection,
            AUTO_APPROVE_PENDING_USERS_SETTING,
        )
    return {
        "success": True,
        "auto_approve_pending_users": auto_approve_pending_users,
    }


@router.put("/settings/registration", response_model=RegistrationSettingsResponse)
async def update_registration_settings(
    settings_data: UpdateRegistrationSettingsRequest,
    admin: dict = Depends(require_admin),
) -> dict:
    with get_connection() as connection:
        set_boolean_setting(
            connection,
            AUTO_APPROVE_PENDING_USERS_SETTING,
            settings_data.auto_approve_pending_users,
        )
        log_activity(
            connection,
            admin["id"],
            admin["username"],
            "registration auto-approve changed",
            "enabled" if settings_data.auto_approve_pending_users else "disabled",
            commit=False,
        )
        connection.commit()
    return {
        "success": True,
        "auto_approve_pending_users": settings_data.auto_approve_pending_users,
    }


@router.get("/settings/ui", response_model=UiSettingsResponse)
async def get_ui_settings(admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        show_graph_tab = get_boolean_setting(
            connection,
            SHOW_GRAPH_TAB_SETTING,
            default=True,
        )
    return {
        "success": True,
        "show_graph_tab": show_graph_tab,
    }


@router.put("/settings/ui", response_model=UiSettingsResponse)
async def update_ui_settings(
    settings_data: UpdateUiSettingsRequest,
    admin: dict = Depends(require_admin),
) -> dict:
    with get_connection() as connection:
        set_boolean_setting(
            connection,
            SHOW_GRAPH_TAB_SETTING,
            settings_data.show_graph_tab,
        )
        log_activity(
            connection,
            admin["id"],
            admin["username"],
            "graph tab visibility changed",
            "enabled" if settings_data.show_graph_tab else "disabled",
            commit=False,
        )
        connection.commit()
    return {
        "success": True,
        "show_graph_tab": settings_data.show_graph_tab,
    }


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


@router.post("/users/{user_id}/unbind-artist")
async def unbind_artist(user_id: int, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as connection:
        updated_user = admin_users_service.unbind_user_artist(connection, user_id=user_id, admin=admin)
    return {"success": True, "message": "Artist unbound", "user": updated_user}


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
