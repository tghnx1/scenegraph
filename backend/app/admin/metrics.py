from __future__ import annotations

import os
import threading
from time import monotonic

from psycopg import Connection

from app.routers.metrics_integrity import get_integrity
from app.routers.metrics_rankings import get_rankings

ADMIN_METRICS_CACHE_TTL_SECONDS = float(os.getenv("ADMIN_METRICS_CACHE_TTL_SECONDS", "15"))
_metrics_cache_lock = threading.Lock()
_metrics_cache: tuple[float, dict] | None = None


def build_metrics_payload(connection: Connection) -> dict:
    integrities = get_integrity(connection)
    rankings = get_rankings(connection)
    return {
        "latest_source_payload": integrities.latest_source_payload if integrities else [],
        "metrics": integrities.integrity_lists if integrities else [],
        "rankings": rankings.top_lists if rankings else [],
    }


def get_cached_metrics_payload(load_connection) -> dict:
    global _metrics_cache

    if ADMIN_METRICS_CACHE_TTL_SECONDS > 0:
        with _metrics_cache_lock:
            if _metrics_cache is not None:
                cached_at, cached_payload = _metrics_cache
                if monotonic() - cached_at < ADMIN_METRICS_CACHE_TTL_SECONDS:
                    return cached_payload

            with load_connection() as connection:
                payload = build_metrics_payload(connection)
            _metrics_cache = (monotonic(), payload)
            return payload

    with load_connection() as connection:
        return build_metrics_payload(connection)
