from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, Header, HTTPException         #Header and HTTPException for the admin operations
from fastapi.middleware.cors import CORSMiddleware
from psycopg import Connection
from fastapi.responses import PlainTextResponse

from datetime import datetime, timedelta, timezone              #for JWT (JSON Web Token)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

security = HTTPBearer()         #security parse that understands jwt-encrypted headers.

from app.db import close_connection_pool, get_connection, get_db, get_connection_pool
from app.recommendation_helpers import extracted_tag_score
from app.schema_preflight import check_schema_tables, schema_preflight_strict_mode
from app.recommendation_job_events import listen_for_recommendation_job_updates
from app.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    Venue,
    VenuesResponse,
    ChangeRoleRequest,
    ArtistClaimRequest,
)

import os
import re       #regular expressions... for registration validation
from time import time       #for rate limit attempts

from passlib.context import CryptContext    # for password hashing

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

BOOTSTRAP_ADMIN_USERNAME = os.getenv("BOOTSTRAP_ADMIN_USERNAME")
BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
BOOTSTRAP_USER_USERNAME = os.getenv("BOOTSTRAP_USER_USERNAME")
BOOTSTRAP_USER_EMAIL = os.getenv("BOOTSTRAP_USER_EMAIL")
BOOTSTRAP_USER_PASSWORD = os.getenv("BOOTSTRAP_USER_PASSWORD")
BOOTSTRAP_USER_ROLE = os.getenv("BOOTSTRAP_USER_ROLE", "artist")
BOOTSTRAP_USER_UPDATE_EXISTING = os.getenv(
    "BOOTSTRAP_USER_UPDATE_EXISTING",
    "false",
).strip().lower() in {"1", "true", "yes", "on"}

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


# Create the configured approved non-admin account once without overwriting existing credentials.
def create_bootstrap_user(connection: Connection) -> None:
    if (
        not BOOTSTRAP_USER_USERNAME
        or not BOOTSTRAP_USER_EMAIL
        or not BOOTSTRAP_USER_PASSWORD
    ):
        return
    if BOOTSTRAP_USER_ROLE not in {"artist", "agent", "admin"}:
        raise RuntimeError("BOOTSTRAP_USER_ROLE must be one of: artist, agent, admin")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            (BOOTSTRAP_USER_USERNAME,),
        )
        existing_user = cursor.fetchone()
        password_hash = pwd_context.hash(BOOTSTRAP_USER_PASSWORD)

        if existing_user is not None:
            if not BOOTSTRAP_USER_UPDATE_EXISTING:
                return
            cursor.execute(
                """
                UPDATE users
                SET email = %s,
                    password_hash = %s,
                    role = %s,
                    status = 'approved',
                    must_change_password = FALSE
                WHERE id = %s
                """,
                (
                    BOOTSTRAP_USER_EMAIL,
                    password_hash,
                    BOOTSTRAP_USER_ROLE,
                    existing_user["id"],
                ),
            )
            connection.commit()
            return

        cursor.execute(
            """
            INSERT INTO users (
                username,
                email,
                password_hash,
                role,
                status,
                must_change_password
            )
            VALUES (%s, %s, %s, %s, 'approved', FALSE)
            """,
            (
                BOOTSTRAP_USER_USERNAME,
                BOOTSTRAP_USER_EMAIL,
                password_hash,
                BOOTSTRAP_USER_ROLE,
            ),
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
        create_bootstrap_user(connection)
    # Open the shared pool during startup so connection issues fail fast.
    get_connection_pool()
    app_instance.state.schema_preflight = schema_report

    if schema_preflight_strict_mode() and schema_report["missingRequiredTables"]:
        missing = ", ".join(schema_report["missingRequiredTables"])
        raise RuntimeError(
            "Database schema preflight failed. Missing required tables: "
            f"{missing}. Run migrations before starting the API."
        )

    recommendation_job_listener = asyncio.create_task(
        listen_for_recommendation_job_updates(),
        name="recommendation-job-updates",
    )
    try:
        yield
    finally:
        recommendation_job_listener.cancel()
        with suppress(asyncio.CancelledError):
            await recommendation_job_listener
        close_connection_pool()


app = FastAPI(title="Berlin Scene Graph API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost:8443",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))
if JWT_SECRET_KEY is None:
    raise RuntimeError("JWT_SECRET_KEY not configured")

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    connection: Connection = Depends(get_db),
) -> dict:
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
        user_id = payload.get("sub")            #in JWT the subject (the user_id)

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, role, status, artist_id
            FROM users
            WHERE id = %s
            """,
            (int(user_id),),
        )
        user = cursor.fetchone()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    if user["status"] != "approved":
        raise HTTPException(status_code=403, detail="Account is not approved")
    
    return user


#admin helper for admin operations (accept, reject, check pending), before the endpoints
def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin token required")
    return current_user


from app.routers.index import router
app.include_router(router, prefix="/api")

def create_access_token(data: dict) -> str:
    to_encode = data.copy()                 #make a copy of the user data

    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})       #add expiration time

    return jwt.encode(              #sign it with secret key
        to_encode,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )

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

#rate limit login-registering attempts
rate_limit_attempts: dict[str, list[float]] = {}

def check_rate_limit(key: str, max_attempts: int = 5, window_seconds: int = 60) -> None:
    now = time()
    attempts = rate_limit_attempts.get(key, [])         #get previous attempts for this key; if none use empty
    attempts = [t for t in attempts if now - t < window_seconds]    #keep only the timestamps t that are only inside the time window

    if len(attempts) >= max_attempts:
        raise HTTPException(status_code=429, detail="Too many attempts. Try later again")

    attempts.append(now)
    rate_limit_attempts[key] = attempts

#when POST /api/login arrives, expect LoginRequest input, execute async login function, return LoginResponse output 
#response_model = LoginResponse means FastAPI should validate and document the returned JSON using LoginResponse  
#async means this function can pause while waiting without blocking whole server
@app.post("/api/login", response_model=LoginResponse, response_model_exclude_none=True)        
async def login(
    login_data: LoginRequest,
    connection: Connection = Depends(get_db),
) -> LoginResponse:
    check_rate_limit(f"login:{login_data.username}")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, password_hash, role, status, must_change_password, artist_id
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
        access_token=create_access_token(
            {
                "sub": str(user["id"]),
                "username": user["username"],
                "role": user["role"],
            }
        ),
        must_change_password=user["must_change_password"],
        artist_id=user["artist_id"],
    )

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")     

def validatate_registration_input(register_data: RegisterRequest) -> str | None:
    if not USERNAME_RE.match(register_data.username):
        return "Username must be 3-32 characters and contain only letters, numbers, _ or -"
    if "@" not in register_data.email or len(register_data.email) > 254:
        return "Invalid email"
    if len(register_data.password) < 8:
        return "Password must be at least 8 characters"
    if len(register_data.password) > 128:
        return "Password is too long"
    return None

@app.post("/api/register", response_model=RegisterResponse, response_model_exclude_none=True)
async def register(
    register_data: RegisterRequest,
    connection: Connection = Depends(get_db)
) -> RegisterResponse:

    check_rate_limit(f"register:{register_data.email}, max_attempts=3, window_seconds=300")

    if register_data.password != register_data.password_confirm:
        return RegisterResponse(
            success=False,
            message="Passwords do not match",
        )
    
    validation_error = validatate_registration_input(register_data)
    if validation_error:
        return RegisterResponse(
            success=False,
            message=validation_error,
        )
    
    if register_data.role not in {"artist", "agent", "admin"}:
        return RegisterResponse(
            success=False,
            message="Invalid role",
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
            INSERT INTO users (username, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (
                register_data.username,
                register_data.email,
                hashed_password,
                register_data.role,
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

def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters"

    if len(password) > 128:
        return "Password is too long"

    return None

@app.post("/api/change-password", response_model=ChangePasswordResponse)
async def change_password(
    password_data: ChangePasswordRequest,           # read json request body into a ChangePasswordRequest object
    connection: Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ChangePasswordResponse:                        # return type... this function should return a ChangePasswordResponse
    if password_data.new_password != password_data.new_password_confirm:
        return ChangePasswordResponse(
            success=False,
            message="New passwords do not match",
        )

    password_error = validate_password(password_data.new_password)

    if password_error:
        return ChangePasswordResponse(
            success=False,
            message=password_error,
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

@app.post("/api/admin/users/{user_id}/activate")
async def activate_user(
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
            (user_id,),
        )
        updated_user = cursor.fetchone()

        if updated_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        
        log_activity(
            connection,
            updated_user["id"],
            updated_user["username"],
            "activation",
            f"Activated by {admin['username']}",
        )

        log_activity(
            connection,
            admin["id"],
            admin["username"],
            "user activated",
            updated_user["username"],
        )
        connection.commit()
    
    return {
        "success": True,
        "message": "User activated",
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
    current_user: dict = Depends(get_current_user),
    connection: Connection = Depends(get_db),
) ->dict:
    log_activity(
        connection,
        current_user["id"],
        current_user["username"],
        "logout",
        "Frontend logout",
    )
    connection.commit()

    return {"success": True, "message": "Logout logged"}

@app.get("/api/admin/activity/export", response_class=PlainTextResponse)
async def export_activity(
    admin: dict = Depends(require_admin),
    connection: Connection = Depends(get_db),
) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, event_type, target, created_at
            FROM activity_log
            ORDER BY created_at DESC
            """
        )
        rows = cursor.fetchall()

    lines = []
    lines.append(
        f"{'id':<4}| {'username':<10}| {'event_type':<28}| {'target':<30}| {'created_at'}"
    )
    lines.append(
        f"{'-' * 4}+{'-' * 11}+{'-' * 29}+{'-' * 31}+{'-' * 30}"
    )
    for row in rows:
        lines.append(
            f"{str(row['id']):<4}| "
            f"{(row['username'] or ''):<10}| "
            f"{row['event_type']:<28}| "
            f"{(row['target'] or ''):<30}| "
            f"{row['created_at']}"
        )

    return "\n".join(lines)

@app.post("/api/admin/users/{user_id}/role")
async def change_user_role(
    user_id: int,
    role_data: ChangeRoleRequest,
    admin: dict = Depends(require_admin),
    connection: Connection = Depends(get_db),
) -> dict:
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
        
        log_activity(
            connection,
            admin["id"],
            admin["username"],
            "user role changed",
            f"{updated_user['username']} -> {updated_user['role']}",
        )

        connection.commit()
    
    return {
        "success": True,
        "message": "User role changed",
        "user": updated_user,
    }

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

PUBLIC_API_KEY=os.getenv("PUBLIC_API_KEY")

def require_public_api_key(api_key: str | None = Header(alias="X-API-Key"),) -> None:
    if not PUBLIC_API_KEY or api_key != PUBLIC_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
@app.get("/api/public/venues")
async def public_venues(
    _: None = Depends(require_public_api_key),          # _: None is because the result is not necessary, just run it
    connection: Connection = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
) -> dict:
    check_rate_limit("public:venues", max_attempts=100, window_seconds=60)

    limit = min(max(limit, 1), 100)     #for pagination
    offset = max(offset, 0)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name
            FROM venues
            ORDER BY name ASC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        rows = cursor.fetchall()

    return {
        "success": True,
        "limit": limit,
        "offset": offset,
        "venues": rows,
    }

@app.get("/api/public/artists")
async def public_artists(
    _: None = Depends(require_public_api_key),         
    connection: Connection = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
) -> dict:
    check_rate_limit("public:artists", max_attempts=100, window_seconds=60)

    limit = min(max(limit, 1), 100)     #for pagination
    offset = max(offset, 0)

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

    return {
        "success": True,
        "limit": limit,
        "offset": offset,
        "artists": rows,
    }

@app.get("/api/public/events")
async def public_events(
    _: None = Depends(require_public_api_key),         
    connection: Connection = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
) -> dict:
    check_rate_limit("public:events", max_attempts=100, window_seconds=60)

    limit = min(max(limit, 1), 100)     #for pagination
    offset = max(offset, 0)

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

    return {
        "success": True,
        "limit": limit,
        "offset": offset,
        "events": rows,
    }

@app.get("/api/public/promoters")
async def public_promoters(
    _: None = Depends(require_public_api_key),         
    connection: Connection = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
) -> dict:
    check_rate_limit("public:promoters", max_attempts=100, window_seconds=60)

    limit = min(max(limit, 1), 100)     #for pagination
    offset = max(offset, 0)

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

    return {
        "success": True,
        "limit": limit,
        "offset": offset,
        "promoters": rows,
    }

@app.get("/api/public/genres")
async def get_public_genres(
    _: None = Depends(require_public_api_key),
    connection: Connection = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name
            FROM genres
            ORDER BY name ASC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        rows = cursor.fetchall()

    return {
        "success": True,
        "limit": limit,
        "offset": offset,
        "genres": rows,
    }

@app.post("/api/artists/{artist_id}/claim")
async def claim_artist_profile(
    artist_id: int,
    claim_data: ArtistClaimRequest,
    current_user: dict = Depends(get_current_user),
    connection: Connection = Depends(get_db),
) -> dict:
    if current_user["role"] != "artist":
        raise HTTPException(status_code=403, detail="Only artists can claim profiles")

    reason = claim_data.reason.strip()
    if len(reason) < 6:
        raise HTTPException(status_code=400, detail="Reason must be at least 6 characters")
    if len(reason) > 80:
        raise HTTPException(status_code=400, detail="Reason must be more concise")


    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM artists WHERE id = %s", (artist_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Artist not found")

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
        connection.commit()

        log_activity(
            connection,
            current_user["id"],
            current_user["username"],
            "artist claim submitted",
            f"artist {artist_id}",
        )
        connection.commit()

    return {"success": True, "message": "Claim submitted", "claim_id": claim["id"]}

@app.get("/api/admin/artist-claims")
async def get_artist_claims(
    admin: dict = Depends(require_admin),
    connection: Connection = Depends(get_db),
) -> dict:
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

@app.post("/api/admin/artist-claims/{claim_id}/approve")
async def approve_artist_claim(
    claim_id: int,
    admin: dict = Depends(require_admin),
    connection: Connection = Depends(get_db),
) -> dict:
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

        connection.commit()

        log_activity(
            connection,
            admin["id"],
            admin["username"],
            "artist claim approved",
            f"{claim['username']} → {claim['artist_name']}",
        )
        connection.commit()

    return {"success": True, "message": "Artist claim approved"}

@app.post("/api/admin/artist-claims/{claim_id}/reject")
async def reject_artist_claim(
    claim_id: int,
    admin: dict = Depends(require_admin),
    connection: Connection = Depends(get_db),
) -> dict:
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
        
        connection.commit()

        log_activity(
            connection,
            admin["id"],
            admin["username"],
            "artist claim rejected",
            f"{claim['username']} → {claim['artist_name']}",
        )
        connection.commit()

    return {"success": True, "message": "Artist claim rejected"}

@app.get("/api/me")
async def get_me(
    current_user: dict = Depends(get_current_user),
) -> dict:
    return {
        "success": True,
        "user_id": current_user["id"],
        "username": current_user["username"],
        "role": current_user["role"],
        "artist_id": current_user["artist_id"],
    }

