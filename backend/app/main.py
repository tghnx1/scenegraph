from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
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
    Venue,
    VenuesResponse,
)

from passlib.context import CryptContext    # for password hashing

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
            SELECT id, username, password_hash
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
    
    return LoginResponse(
        success=True,
        message="Login successful",
        user_id=user["id"],
        username=user["username"],
        access_token="dummy-token",
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

        connection.commit() # ensure to save the changes...
    
    return RegisterResponse(
        success=True,
        message="Registration successful",
        user_id=created_user["id"],
    )

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
