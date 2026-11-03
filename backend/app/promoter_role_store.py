"""Read classification inputs and persist decisions without changing RA records."""

from __future__ import annotations

from psycopg import Connection
from psycopg.rows import tuple_row

from app.promoter_role_llm import RoleResponse
from app.promoter_roles import CLASSIFIER_VERSION, EventRoleInput, PromoterProfile, normalize_name, role_input_hash


class EventInputChanged(RuntimeError):
    """The event changed while a model request was in flight."""


def load_event_input(connection: Connection, event_id: int, *, lock: bool = False) -> EventRoleInput | None:
    with connection.cursor(row_factory=tuple_row) as cursor:
        cursor.execute(
            "SELECT id, title, description_text, venue_id FROM events WHERE id = %s" + (" FOR UPDATE" if lock else ""),
            (event_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        _, title, description, venue_id = row
        venue_name = None
        if venue_id is not None:
            cursor.execute("SELECT name FROM venues WHERE id = %s", (venue_id,))
            venue_row = cursor.fetchone()
            venue_name = venue_row[0] if venue_row else None
        cursor.execute("""
            SELECT p.id, p.name, CASE WHEN im.status = 'confirmed' THEN im.identity_id END
            FROM event_promoters ep JOIN promoters p ON p.id = ep.promoter_id
            LEFT JOIN promoter_identity_member im ON im.promoter_id = p.id
            WHERE ep.event_id = %s ORDER BY p.id
        """, (event_id,))
        profiles = tuple(PromoterProfile(int(id_), name, identity) for id_, name, identity in cursor.fetchall())
    return EventRoleInput(event_id, title, description, venue_id, venue_name, profiles)


def save_llm_roles(connection: Connection, source: EventRoleInput, response: RoleResponse, *, method: str = "llm") -> None:
    """Recheck the event under its import lock; never overwrite a manual decision."""
    if method not in {"llm", "rule"}:
        raise ValueError("invalid automatic classification method")
    current = load_event_input(connection, source.event_id, lock=True)
    source_hash = role_input_hash(source)
    if current is None or role_input_hash(current) != source_hash:
        raise EventInputChanged("event input changed during classification")
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE promoter_event_role SET needs_review = TRUE, updated_at = now()
            WHERE event_id = %s AND method = 'manual' AND input_hash <> %s AND NOT needs_review
        """, (source.event_id, source_hash))
        for decision in response.roles:
            cursor.execute("""
                INSERT INTO promoter_event_role
                    (event_id, promoter_id, role, confidence, reason_code, evidence, method, classifier_version, input_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id, promoter_id) DO UPDATE SET
                    role = EXCLUDED.role, confidence = EXCLUDED.confidence,
                    reason_code = EXCLUDED.reason_code, evidence = EXCLUDED.evidence,
                    method = EXCLUDED.method, classifier_version = EXCLUDED.classifier_version,
                    input_hash = EXCLUDED.input_hash, classified_at = now(), updated_at = now()
                WHERE promoter_event_role.method <> 'manual'
            """, (source.event_id, decision.promoter_id, decision.role, decision.confidence,
                  "explicit_presenter" if method == "rule" else "model_evidence", decision.evidence,
                  method, CLASSIFIER_VERSION, source_hash))
        for candidate in response.candidates:
            normalized = normalize_name(candidate.name)
            if not normalized:
                continue
            cursor.execute("""
                INSERT INTO event_organizer_candidate
                    (event_id, name, normalized_name, evidence, confidence, classifier_version, input_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id, normalized_name, input_hash, classifier_version) DO NOTHING
            """, (source.event_id, candidate.name, normalized, candidate.evidence,
                  candidate.confidence, CLASSIFIER_VERSION, source_hash))
