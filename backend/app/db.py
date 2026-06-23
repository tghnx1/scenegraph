import os
import threading
from collections.abc import Generator

import psycopg
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row


DATABASE_URL = os.environ["DATABASE_URL"]
DATABASE_POOL_MIN_SIZE = int(os.getenv("DATABASE_POOL_MIN_SIZE", "1"))
DATABASE_POOL_MAX_SIZE = int(os.getenv("DATABASE_POOL_MAX_SIZE", "5"))

_connection_pool: ConnectionPool | None = None
_connection_pool_lock = threading.Lock()


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


def get_connection() -> psycopg.Connection:
    return get_connection_pool().connection()


def get_db() -> Generator[psycopg.Connection, None, None]:
    with get_connection() as connection:
        yield connection
