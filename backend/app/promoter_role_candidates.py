"""Conservative read-only matching of text candidates to RA profiles."""

from __future__ import annotations

from dataclasses import dataclass

from psycopg import Connection
from psycopg.rows import tuple_row

from app.promoter_roles import normalize_name


@dataclass(frozen=True, slots=True)
class CandidateMatch:
    promoter_id: int
    ra_promoter_id: str
    name: str
    confirmed_identity_id: int | None


def find_candidate_matches(connection: Connection, candidate_name: str) -> tuple[CandidateMatch, ...]:
    """Return exact normalized name matches as proposals, never create or confirm a profile."""
    target = normalize_name(candidate_name)
    if not target:
        return ()
    with connection.cursor(row_factory=tuple_row) as cursor:
        cursor.execute("""
            SELECT p.id, p.ra_promoter_id, p.name,
                   CASE WHEN im.status = 'confirmed' THEN im.identity_id END
            FROM promoters p LEFT JOIN promoter_identity_member im ON im.promoter_id = p.id
            ORDER BY p.id
        """)
        return tuple(CandidateMatch(int(id_), str(ra_id), name, int(identity) if identity is not None else None)
                     for id_, ra_id, name, identity in cursor.fetchall() if normalize_name(name) == target)
