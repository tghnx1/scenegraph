"""Resolve current organizer credits without modifying Resident Advisor data."""

from __future__ import annotations

from dataclasses import dataclass

from psycopg import Connection
from psycopg.rows import tuple_row

from app.promoter_role_store import load_event_input
from app.promoter_roles import CLASSIFIER_VERSION, role_input_hash


@dataclass(frozen=True, slots=True)
class EligiblePromoter:
    canonical_id: int
    source_ids: tuple[int, ...]


def eligible_promoters(connection: Connection, event_id: int, expected_config_hash: str) -> tuple[EligiblePromoter, ...]:
    """Return only current organizer/both credits, deduplicated by confirmed identity.

    Unknown, stale, removed and unreviewed roles cannot create a recommendation.
    Manual roles are valid only for the exact input they were reviewed against.
    """
    event = load_event_input(connection, event_id)
    if event is None:
        return ()
    current_hash = role_input_hash(event)
    with connection.cursor(row_factory=tuple_row) as cursor:
        cursor.execute("""
            SELECT 1 FROM promoter_event_classification
            WHERE event_id = %s AND input_hash = %s AND config_hash = %s AND classifier_version = %s
        """, (event_id, current_hash, expected_config_hash, CLASSIFIER_VERSION))
        automatic_current = cursor.fetchone() is not None
        cursor.execute("""
            SELECT promoter_id, method FROM promoter_event_role
            WHERE event_id = %s AND input_hash = %s AND role IN ('organizer', 'both')
              AND NOT needs_review AND (method = 'manual' OR classifier_version = %s)
        """, (event_id, current_hash, CLASSIFIER_VERSION))
        roles = {int(promoter_id): method for promoter_id, method in cursor.fetchall()}
        identity_ids = [p.identity_id for p in event.promoters if p.identity_id is not None]
        canonical = {}
        if identity_ids:
            cursor.execute("""
                SELECT identity_id, min(promoter_id) FROM promoter_identity_member
                WHERE status = 'confirmed' AND identity_id = ANY(%s) GROUP BY identity_id
            """, (identity_ids,))
            canonical = {int(identity): int(promoter) for identity, promoter in cursor.fetchall()}
    result: dict[int, list[int]] = {}
    for profile in event.promoters:
        method = roles.get(profile.id)
        if method is None or not automatic_current:
            continue
        identity = canonical.get(profile.identity_id, profile.id)
        result.setdefault(identity, []).append(profile.id)
    return tuple(EligiblePromoter(key, tuple(sorted(value))) for key, value in sorted(result.items()))
