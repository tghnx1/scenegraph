import os
from collections.abc import Generator

import psycopg
from psycopg.rows import dict_row


DATABASE_URL = os.environ["DATABASE_URL"]


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def get_db() -> Generator[psycopg.Connection, None, None]:
    with get_connection() as connection:
        yield connection
