from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg import Connection

from app.db import get_db
from app.recommendation_helpers import extracted_tag_score
from app.schemas import (
    LoginRequest,
    LoginResponse,
    Venue,
    VenuesResponse,
)


app = FastAPI(title="Berlin Scene Graph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers.index import router
app.include_router(router, prefix="/api")

dummy_users = [
    {"id": 1, "username": "maksim", "password": "12345"},
    {"id": 2, "username": "howard", "password": "12345"},
    {"id": 3, "username": "tarcisio", "password": "12345"},
    {"id": 4, "username": "herold", "password": "12345"},
    {"id": 5, "username": "aaron", "password": "12345"},
]

@app.get("/health")
async def health(connection: Connection = Depends(get_db)) -> dict[str, str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 AS ready")
        ready = cursor.fetchone()["ready"]

    return {"status": "ok", "database": "ok" if ready == 1 else "error"}


@app.get("/api")
async def root() -> dict[str, str]:
    return {"message": "Berlin Scene Graph backend is running."}

#when POST /api/login arrives, expect LoginRequest input, execute async login function, return LoginResponse output 
#response_model = LoginResponse means FastAPI should validate and document the returned JSON using LoginResponse  
#async means this function can pause while waiting without blocking whole server
@app.post("/api/login", response_model=LoginResponse, response_model_exclude_none=True)        
async def login(login_data: LoginRequest) -> LoginResponse:
    for user in dummy_users:
        if (user["username"] == login_data.username and user["password"] == login_data.password):
            return LoginResponse(
                success=True,
                message="Login successful",
                user_id=user["id"],
                username=user["username"],
                access_token="dummy-token",
            )
    return LoginResponse(
        success=False,
        message="Invalid username or password"
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
