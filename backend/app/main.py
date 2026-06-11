from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException         #Header and HTTPException for the admin operations
from fastapi.middleware.cors import CORSMiddleware
from psycopg import Connection

from app.db import get_connection, get_db
from app.recommendation_helpers import extracted_tag_score
from app.schema_preflight import check_schema_tables, schema_preflight_strict_mode
from app.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    Venue,
    VenuesResponse,
)

import os

from passlib.context import CryptContext    # for password hashing

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

BOOTSTRAP_ADMIN_USERNAME = os.getenv("BOOTSTRAP_ADMIN_USERNAME")
BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")

def create_bootstrap_admin(connection: Connection) -> None:         #like void
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE role = 'admin'
            LIMIT 1     
            """                 #limit 1 is for finding at most one admin
        )

        admin = cursor.fetchone()

        if admin is not None:
            return
        if (
            not BOOTSTRAP_ADMIN_USERNAME
            or not BOOTSTRAP_ADMIN_EMAIL
            or not BOOTSTRAP_ADMIN_PASSWORD
        ):
            print("Bootstrap admin variables missing")
            return
        
        hashed_password = pwd_context.hash(BOOTSTRAP_ADMIN_PASSWORD)

        cursor.execute(
            """
            INSERT INTO users
            (
                username,
                email,
                password_hash,
                role,
                status,
                must_change_password
            )
            VALUES
            (
                %s,
                %s,
                %s,
                'admin',
                'approved',
                TRUE
            )
            """,
            (
                BOOTSTRAP_ADMIN_USERNAME,
                BOOTSTRAP_ADMIN_EMAIL,
                hashed_password,              
            )
        )

        connection.commit()

def log_activity(
        connection: Connection,
        user_id: int | None,
        username: str | None,
        event_type: str,
        target: str | None = None,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO activity_log (user_id, username, event_type, target)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, username, event_type, target),
        )
    connection.commit()

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    schema_report: dict[str, object] = {
        "status": "unknown",
        "checkedAt": None,
        "requiredTableCount": 0,
        "optionalTableCount": 0,
        "missingRequiredTables": [],
        "missingOptionalTables": [],
    }
    with get_connection() as connection:
        schema_report = check_schema_tables(connection)
        create_bootstrap_admin(connection)
    app_instance.state.schema_preflight = schema_report

    if schema_preflight_strict_mode() and schema_report["missingRequiredTables"]:
        missing = ", ".join(schema_report["missingRequiredTables"])
        raise RuntimeError(
            "Database schema preflight failed. Missing required tables: "
            f"{missing}. Run migrations before starting the API."
        )

    yield


app = FastAPI(title="Berlin Scene Graph API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers.index import router
app.include_router(router, prefix="/api")

#admin helper for admin operations (accept, reject, check pending), before the endpoints
def require_admin(
    admin_username: str = Header(alias="X-Admin-Username"),      # when a request arrives, read the HTTP header called X-Admin-Username and put it in admin_username
    connection: Connection = Depends(get_db),
) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, role, status
            FROM users
            WHERE username = %s
            """,
            (admin_username,),
        )
        admin = cursor.fetchone()

    if(
        admin is None
        or admin["role"] != "admin"
        or admin["status"] != "approved"
    ):
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )
    return admin


@app.get("/health")
async def health(connection: Connection = Depends(get_db)) -> dict[str, object]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 AS ready")
        ready = cursor.fetchone()["ready"]

    schema_report = getattr(
        app.state,
        "schema_preflight",
        {
            "status": "unknown",
            "checkedAt": None,
            "requiredTableCount": 0,
            "optionalTableCount": 0,
            "missingRequiredTables": [],
            "missingOptionalTables": [],
        },
    )
    database_status = "ok" if ready == 1 else "error"
    overall_status = (
        "ok"
        if database_status == "ok" and schema_report["status"] in {"ok", "degraded"}
        else "error"
    )

    return {
        "status": overall_status,
        "database": database_status,
        "schema": schema_report,
    }


@app.get("/health/schema")
@app.get("/api/health/schema")
async def health_schema() -> dict[str, object]:
    return getattr(
        app.state,
        "schema_preflight",
        {
            "status": "unknown",
            "checkedAt": None,
            "requiredTableCount": 0,
            "optionalTableCount": 0,
            "missingRequiredTables": [],
            "missingOptionalTables": [],
        },
    )


@app.get("/api")
async def root() -> dict[str, str]:
    return {"message": "Berlin Scene Graph backend is running."}

#when POST /api/login arrives, expect LoginRequest input, execute async login function, return LoginResponse output 
#response_model = LoginResponse means FastAPI should validate and document the returned JSON using LoginResponse  
#async means this function can pause while waiting without blocking whole server
@app.post("/api/login", response_model=LoginResponse, response_model_exclude_none=True)        
async def login(
    login_data: LoginRequest,
    connection: Connection = Depends(get_db),
) -> LoginResponse:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, password_hash, role, status, must_change_password
            FROM users
            WHERE username = %s
            """,
            (login_data.username,),
        )
        user = cursor.fetchone()

    if user is None:
        return LoginResponse(
            success=False,
            message="Invalid username or password",
        )
    
    if not pwd_context.verify(login_data.password, user["password_hash"]):
        return LoginResponse(
            success=False,
            message="Invalid username or password",
        )

    if user["status"] != "approved":
        return LoginResponse(
            success=False,
            message="Account is not approved"
        )
    
    log_activity(
        connection,
        user["id"],
        user["username"],
        "login",
        "Login page",
    )
    connection.commit()
    
    return LoginResponse(
        success=True,
        message="Login successful",
        user_id=user["id"],
        username=user["username"],
        role=user["role"],
        access_token="dummy-token",
        must_change_password=user["must_change_password"],
    )

@app.post("/api/register", response_model=RegisterResponse, response_model_exclude_none=True)
async def register(
    register_data: RegisterRequest,
    connection: Connection = Depends(get_db),
) -> RegisterResponse:

    if register_data.password != register_data.password_confirm:
        return RegisterResponse(
            success=False,
            message="Passwords do not match",
        )
    
    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE username = %s OR email = %s
            """,
            (register_data.username, register_data.email)
        )

        existing_user = cursor.fetchone()

        if existing_user is not None:
            return RegisterResponse(
                success=False,
                message="Username or email already exists",
            )
        
        hashed_password = pwd_context.hash(register_data.password)

        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (
                register_data.username,
                register_data.email,
                hashed_password,
            ),
        )

        created_user = cursor.fetchone()

        log_activity(
            connection,
            created_user["id"],
            register_data.username,
            "registration",
            "User account",
        )
        connection.commit() # ensure to save the changes...
    
    return RegisterResponse(
        success=True,
        message="Registration successful",
        user_id=created_user["id"],
    )

@app.post("/api/change-password", response_model=ChangePasswordResponse)
async def change_password(
    password_data: ChangePasswordRequest,           # read json request body into a ChangePasswordRequest object
    connection: Connection = Depends(get_db),
) -> ChangePasswordResponse:                        # return type... this function should return a ChangePasswordResponse
    if password_data.new_password != password_data.new_password_confirm:
        return ChangePasswordResponse(
            success=False,
            message="New passwords do not match",
        )
    
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, password_hash, status
            FROM users
            WHERE username = %s
            """,
            (password_data.username,),
        )
        user = cursor.fetchone()

        if user is None:
            return ChangePasswordResponse(
                success=False,
                message="Invalid username or password",
            )
        
        if user["status"] != "approved":
            return ChangePasswordResponse(
                success=False,
                message="Account is not approved"
            )
        
        if not pwd_context.verify(password_data.current_password, user["password_hash"]):
            return ChangePasswordResponse(
                success=False,
                message="Invalid username or password",
            )
        
        if pwd_context.verify(password_data.new_password, user["password_hash"]):
            return ChangePasswordResponse(
                success=False,
                message="New password must be different from current password",
            )
        
        new_hashed_password = pwd_context.hash(password_data.new_password)

        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s,
                must_change_password = FALSE
            WHERE id = %s
            """,
            (
                new_hashed_password,
                user["id"],
            ),
        )

        log_activity(
            connection,
            user["id"],
            user["username"],
            "password change",
            "Own account",
        )

        connection.commit()

    return ChangePasswordResponse(
        success=True,
        message="Password changed successfully",
    )

@app.get("/api/admin/users/pending")
async def list_pending_users(
    admin: dict = Depends(require_admin),
    connection: Connection = Depends(get_db),
) -> dict:
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
    
    return {
        "success": True,
        "users": users,
    }

@app.post("/api/admin/users/{user_id}/approve")
async def approve_user(
    user_id: int,
    admin: dict = Depends(require_admin),
    connection: Connection = Depends(get_db),
) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE users
            SET status = 'approved'
            WHERE id = %s
            RETURNING id, username, email, role, status
            """,
            (user_id,)
        )
        updated_user = cursor.fetchone()
        connection.commit()
    
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    log_activity(
        connection,
        admin["id"],
        admin["username"],
        "user approved",
        updated_user["username"],
    )
    connection.commit()

    return {
        "success": True,
        "message": "User approved",
        "user": updated_user,
    }

@app.post("/api/admin/users/{user_id}/reject")
async def reject_user(
    user_id: int,
    admin: dict = Depends(require_admin),
    connection: Connection = Depends(get_db),
) -> dict:
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
        connection.commit()
    
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    log_activity(
        connection,
        admin["id"],
        admin["username"],
        "user registration rejected",
        updated_user["username"],
    )
    connection.commit()

    return {
        "success": True,
        "message": "User rejected",
        "user": updated_user,
    }


@app.post("/api/admin/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    admin: dict = Depends(require_admin),
    connection: Connection = Depends(get_db),
) -> dict:
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
        
        log_activity(
            connection,
            updated_user["id"],
            updated_user["username"],
            "deactivation",
            f"Deactivated by {admin['username']}",
        )

        log_activity(
            connection,
            admin["id"],
            admin["username"],
            "user deactivated",
            updated_user["username"],
        )
        connection.commit()
    
    return {
        "success": True,
        "message": "User deactivated",
        "user": updated_user,
    }

@app.get("/api/admin/activity")
async def list_activity(
    admin: dict = Depends(require_admin),
    connection: Connection = Depends(get_db),
) -> dict:
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
    
    return {
        "success": True,
        "activity": rows,
    }

@app.get("/api/admin/users")
async def list_users(
    admin: dict = Depends(require_admin),
    connection: Connection = Depends(get_db),
) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, email, role, status, created_at
            FROM users
            ORDER BY created_at DESC
            """
        )
        users = cursor.fetchall()

    return {
        "success": True,
        "users": users,
    }

@app.post("/api/logout")
async def logout(
    logout_data: LoginRequest,
    connection: Connection = Depends(get_db),
) ->dict:
    log_activity(
        connection,
        None,
        logout_data.username,
        "logout",
        "Frontend logout",
    )
    connection.commit()

    return {"success": True, "message": "Logout logged"}

@app.get("/api/venues", response_model=VenuesResponse)
async def list_venues(connection: Connection = Depends(get_db)) -> VenuesResponse:
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
