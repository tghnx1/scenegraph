"""Explicit, audited and reversible confirmation of promoter profile aliases."""

from __future__ import annotations

from psycopg import Connection

IDENTITY_LOCK = 0x534750524F4C4549
REVIEW_VERSION = "manual-v1"


def _check_reason(reason: str) -> str:
    value = reason.strip()
    if not value or len(value) > 500:
        raise ValueError("review reason must contain 1 to 500 characters")
    return value


def confirm_profiles(connection: Connection, promoter_ids: tuple[int, ...], reason: str) -> int:
    """Confirm profiles as one identity; refuse implicit merges of existing identities."""
    reason = _check_reason(reason)
    if len(promoter_ids) < 2 or len(set(promoter_ids)) != len(promoter_ids):
        raise ValueError("at least two unique profiles are required")
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (IDENTITY_LOCK,))
        cursor.execute("SELECT id FROM promoters WHERE id = ANY(%s) ORDER BY id FOR UPDATE", (list(promoter_ids),))
        if len(cursor.fetchall()) != len(promoter_ids):
            raise ValueError("one or more profiles do not exist")
        cursor.execute("SELECT promoter_id, identity_id, status FROM promoter_identity_member WHERE promoter_id = ANY(%s) FOR UPDATE", (list(promoter_ids),))
        members = {int(p): (int(i), status) for p, i, status in cursor.fetchall()}
        identities = {item[0] for item in members.values()}
        if len(identities) > 1:
            raise ValueError("profiles belong to different identities; review separately")
        if identities:
            identity_id = next(iter(identities))
        else:
            cursor.execute("INSERT INTO promoter_identity DEFAULT VALUES RETURNING id")
            identity_id = int(cursor.fetchone()[0])
        for promoter_id in sorted(promoter_ids):
            previous_status = members.get(promoter_id, (identity_id, None))[1]
            if previous_status == "confirmed":
                continue
            cursor.execute("""
                INSERT INTO promoter_identity_member (promoter_id, identity_id, status, reason, version)
                VALUES (%s, %s, 'confirmed', %s, %s)
                ON CONFLICT (promoter_id) DO UPDATE SET status = 'confirmed', reason = EXCLUDED.reason,
                  version = EXCLUDED.version, updated_at = now()
            """, (promoter_id, identity_id, reason, REVIEW_VERSION))
            cursor.execute("""
                INSERT INTO promoter_identity_audit (promoter_id, identity_id, previous_status, new_status, reason, version)
                VALUES (%s, %s, %s, 'confirmed', %s, %s)
            """, (promoter_id, identity_id, previous_status, reason, REVIEW_VERSION))
    return identity_id


def unconfirm_profile(connection: Connection, promoter_id: int, reason: str) -> None:
    """Undo confirmation without deleting the RA profile or its history."""
    reason = _check_reason(reason)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (IDENTITY_LOCK,))
        cursor.execute("SELECT identity_id FROM promoter_identity_member WHERE promoter_id = %s AND status = 'confirmed' FOR UPDATE", (promoter_id,))
        row = cursor.fetchone()
        if row is None:
            raise LookupError("confirmed identity membership not found")
        cursor.execute("UPDATE promoter_identity_member SET status = 'proposed', reason = %s, version = %s, updated_at = now() WHERE promoter_id = %s", (reason, REVIEW_VERSION, promoter_id))
        cursor.execute("""
            INSERT INTO promoter_identity_audit (promoter_id, identity_id, previous_status, new_status, reason, version)
            VALUES (%s, %s, 'confirmed', 'proposed', %s, %s)
        """, (promoter_id, row[0], reason, REVIEW_VERSION))
