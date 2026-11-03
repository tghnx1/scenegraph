"""Provide a transaction-local, role-filtered relation to recommendation SQL."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection

from app.promoter_roles import CLASSIFIER_VERSION


@contextmanager
def role_filtered_relation(connection: Connection, config_hash: str) -> Iterator[None]:
    """Shadow event_promoters only within this transaction and this connection.

    Existing queries can keep their relation name. The SQL view was bound to the
    original RA tables at migration time, so creating the temporary table does
    not change its source. Failure rolls back the temporary table with the scope.
    Callers must not commit inside the scope.
    """
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TEMPORARY TABLE event_promoters ON COMMIT DROP AS
                SELECT event_id, promoter_id FROM promoter_role_eligible_links
                WHERE config_hash = %s AND classifier_version = %s
            """, (config_hash, CLASSIFIER_VERSION))
            cursor.execute("CREATE INDEX ON event_promoters (event_id)")
            cursor.execute("CREATE INDEX ON event_promoters (promoter_id)")
        yield
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE pg_temp.event_promoters")
