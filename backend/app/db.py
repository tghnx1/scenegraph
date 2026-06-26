import os
import threading
import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
from time import perf_counter
from collections.abc import Generator

import psycopg
from psycopg_pool import ConnectionPool
from psycopg_pool import PoolTimeout
from psycopg.rows import dict_row


DATABASE_URL = os.environ["DATABASE_URL"]
DATABASE_POOL_MIN_SIZE = int(os.getenv("DATABASE_POOL_MIN_SIZE", "1"))
DATABASE_POOL_MAX_SIZE = int(os.getenv("DATABASE_POOL_MAX_SIZE", "5"))
DATABASE_POOL_ACQUIRE_WARN_SECONDS = float(
    os.getenv("DATABASE_POOL_ACQUIRE_WARN_SECONDS", "0.5")
)
DATABASE_CONNECTION_HOLD_WARN_SECONDS = float(
    os.getenv("DATABASE_CONNECTION_HOLD_WARN_SECONDS", "2.0")
)

_connection_pool: ConnectionPool | None = None
_connection_pool_lock = threading.Lock()
_current_request_path: ContextVar[str] = ContextVar(
    "current_request_path",
    default="unknown",
)
logger = logging.getLogger(__name__)


def get_connection_pool() -> ConnectionPool:
    """Return the shared PostgreSQL connection pool for short-lived database work."""
    global _connection_pool
    if _connection_pool is None:
        with _connection_pool_lock:
            if _connection_pool is None:
                _connection_pool = ConnectionPool(
                    conninfo=DATABASE_URL,
                    min_size=DATABASE_POOL_MIN_SIZE,
                    max_size=DATABASE_POOL_MAX_SIZE,
                    open=True,
                    kwargs={"row_factory": dict_row},
                )
    return _connection_pool


def close_connection_pool() -> None:
    """Close the shared PostgreSQL connection pool if the process is shutting down."""
    global _connection_pool
    if _connection_pool is None:
        return
    with _connection_pool_lock:
        if _connection_pool is not None:
            _connection_pool.close()
            _connection_pool = None


@contextmanager
def get_connection() -> Generator[psycopg.Connection, None, None]:
    """Yield one pooled database connection and log slow checkout/hold times."""
    path = _current_request_path.get()
    acquire_started_at = perf_counter()
    connection_context = get_connection_pool().connection()

    try:
        with connection_context as connection:
            acquired_at = perf_counter()
            acquire_seconds = acquired_at - acquire_started_at
            if acquire_seconds >= DATABASE_POOL_ACQUIRE_WARN_SECONDS:
                logger.warning(
                    "Slow database pool checkout path=%s acquire_seconds=%.3f stats=%s",
                    path,
                    acquire_seconds,
                    _pool_stats(),
                )

            try:
                yield connection
            finally:
                hold_seconds = perf_counter() - acquired_at
                if hold_seconds >= DATABASE_CONNECTION_HOLD_WARN_SECONDS:
                    logger.warning(
                        "Long database connection hold path=%s hold_seconds=%.3f stats=%s",
                        path,
                        hold_seconds,
                        _pool_stats(),
                    )
    except PoolTimeout:
        logger.exception(
            "Database pool checkout timeout path=%s waited_seconds=%.3f stats=%s",
            path,
            perf_counter() - acquire_started_at,
            _pool_stats(),
        )
        raise


def set_current_request_path(path: str) -> Token[str]:
    """Store the active HTTP path so DB pool diagnostics can identify slow requests."""
    return _current_request_path.set(path)


def reset_current_request_path(token: Token[str]) -> None:
    """Restore the previous HTTP path after a request leaves the middleware stack."""
    _current_request_path.reset(token)


def _pool_stats() -> dict[str, int | float] | None:
    """Return current pool counters when psycopg exposes them."""
    pool = _connection_pool
    if pool is None:
        return None
    try:
        return pool.get_stats()
    except Exception:
        return None

