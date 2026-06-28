from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap import create_bootstrap_admin, create_bootstrap_user
from app.db import (
    close_connection_pool,
    get_connection,
    get_connection_pool,
    reset_current_request_path,
    set_current_request_path,
)
from app.recommendations.helpers import extracted_tag_score
from app.recommendations.job_events import listen_for_recommendation_job_updates
from app.routers.index import router as api_router
from app.schema_preflight import check_schema_tables, schema_preflight_strict_mode


_lifespan_lock = threading.Lock()
_lifespan_instances = 0


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
    with _lifespan_lock:
        global _lifespan_instances
        _lifespan_instances += 1
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
        with _lifespan_lock:
            _lifespan_instances -= 1
            if _lifespan_instances == 0:
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


@app.middleware("http")
async def attach_request_path_to_db_diagnostics(request: Request, call_next):
    token = set_current_request_path(f"{request.method} {request.url.path}")
    try:
        return await call_next(request)
    finally:
        reset_current_request_path(token)


@app.get("/health")
async def health() -> dict[str, object]:
    with get_connection() as connection:
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


app.include_router(api_router, prefix="/api")
