"""Provide a transaction-local, role-filtered relation to recommendation SQL."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from psycopg import Connection

from app.promoter_roles import CLASSIFIER_VERSION

_ROLE_FILTER_ACTIVE: ContextVar[bool] = ContextVar("promoter_role_filter_active", default=False)


def role_filter_active() -> bool:
    return _ROLE_FILTER_ACTIVE.get()


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
                SELECT event_id, promoter_id, source_promoter_ids FROM promoter_role_eligible_links
                WHERE config_hash = %s AND classifier_version = %s
            """, (config_hash, CLASSIFIER_VERSION))
            cursor.execute("CREATE INDEX ON event_promoters (event_id)")
            cursor.execute("CREATE INDEX ON event_promoters (promoter_id)")
            cursor.execute("""
                CREATE TEMPORARY TABLE promoter_role_identity_map ON COMMIT DROP AS
                SELECT member.promoter_id AS source_id, min(peer.promoter_id) AS canonical_id
                FROM promoter_identity_member member JOIN promoter_identity_member peer
                  ON peer.identity_id = member.identity_id AND peer.status = 'confirmed'
                WHERE member.status = 'confirmed' GROUP BY member.promoter_id
            """)
            cursor.execute("CREATE INDEX ON promoter_role_identity_map (source_id)")
        token = _ROLE_FILTER_ACTIVE.set(True)
        try:
            yield
        finally:
            _ROLE_FILTER_ACTIVE.reset(token)
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE pg_temp.event_promoters")
            cursor.execute("DROP TABLE pg_temp.promoter_role_identity_map")
