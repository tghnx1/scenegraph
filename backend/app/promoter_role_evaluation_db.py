"""Evaluate frozen reviewed links against current automatic classifications."""

from __future__ import annotations

from dataclasses import dataclass
import re

from psycopg import Connection
from psycopg.rows import tuple_row

from app.promoter_role_evaluation import ReviewedRole, RoleQuality, evaluate_roles
from app.promoter_role_store import load_event_input
from app.promoter_roles import CLASSIFIER_VERSION, role_input_hash


@dataclass(frozen=True, slots=True)
class ReviewedCase:
    ra_event_id: str
    ra_promoter_id: str
    expected_organizer: bool


@dataclass(frozen=True, slots=True)
class EvaluatedCase:
    ra_event_id: str
    ra_promoter_id: str
    expected_organizer: bool
    predicted_role: str
    available: bool


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    cases: tuple[EvaluatedCase, ...]
    quality: RoleQuality
    unavailable: int
    release_ready: bool


def evaluate_current_cases(connection: Connection, cases: tuple[ReviewedCase, ...], *,
                           config_hash: str, representative: bool) -> EvaluationReport:
    """Treat absent or stale decisions as unknown; manual overrides are not model output."""
    results: list[EvaluatedCase] = []
    scores: list[ReviewedRole] = []
    for case in cases:
        with connection.cursor(row_factory=tuple_row) as cursor:
            cursor.execute("""
                SELECT e.id, p.id FROM events e JOIN event_promoters ep ON ep.event_id = e.id
                JOIN promoters p ON p.id = ep.promoter_id
                WHERE e.ra_event_id = %s AND p.ra_promoter_id = %s
            """, (case.ra_event_id, case.ra_promoter_id))
            pair = cursor.fetchone()
        predicted = "unknown"
        available = False
        if pair:
            event = load_event_input(connection, int(pair[0]))
            if event is not None:
                with connection.cursor(row_factory=tuple_row) as cursor:
                    cursor.execute("""
                        SELECT r.role FROM promoter_event_role r
                        JOIN promoter_event_classification c ON c.event_id = r.event_id AND c.input_hash = r.input_hash
                        WHERE r.event_id = %s AND r.promoter_id = %s AND r.method <> 'manual'
                          AND NOT r.needs_review AND r.classifier_version = %s AND c.classifier_version = %s
                          AND c.config_hash = %s AND c.input_hash = %s
                    """, (pair[0], pair[1], CLASSIFIER_VERSION, CLASSIFIER_VERSION, config_hash, role_input_hash(event)))
                    row = cursor.fetchone()
                if row:
                    predicted = row[0]
                    available = True
        results.append(EvaluatedCase(case.ra_event_id, case.ra_promoter_id, case.expected_organizer, predicted, available))
        scores.append(ReviewedRole(case.expected_organizer, predicted))
    quality = evaluate_roles(tuple(scores))
    unavailable = sum(not result.available for result in results)
    return EvaluationReport(tuple(results), quality, unavailable,
                            representative and unavailable == 0 and quality.passes)


def record_quality_review(connection: Connection, report: EvaluationReport, *, config_hash: str,
                          manifest_sha256: str, reviewer: str) -> int:
    """Record only a complete representative review that meets both quality thresholds."""
    reviewer = reviewer.strip()
    if (not report.release_ready or not report.cases or report.unavailable != 0
            or any(not case.available for case in report.cases)
            or not reviewer or len(reviewer) > 200 or not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256)):
        raise ValueError("review is incomplete, below threshold, or has invalid provenance")
    quality = report.quality
    calculated = evaluate_roles(tuple(ReviewedRole(case.expected_organizer, case.predicted_role) for case in report.cases))
    if quality != calculated or not calculated.passes:
        raise ValueError("review results do not match its cases")
    with connection.cursor(row_factory=tuple_row) as cursor:
        cursor.execute("""
            INSERT INTO promoter_role_quality_review
              (config_hash, classifier_version, manifest_sha256, true_positive, true_negative,
               false_positive, false_negative, unknown_count, representative, reviewer)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true, %s) RETURNING id
        """, (config_hash, CLASSIFIER_VERSION, manifest_sha256, quality.true_positive, quality.true_negative,
              quality.false_positive, quality.false_negative, quality.unknown, reviewer))
        return int(cursor.fetchone()[0])


def has_quality_review(connection: Connection, config_hash: str) -> bool:
    """A review is tied to the exact model configuration and classifier version."""
    with connection.cursor(row_factory=tuple_row) as cursor:
        cursor.execute("""
            SELECT 1 FROM promoter_role_quality_review r
            WHERE r.config_hash = %s AND r.classifier_version = %s
              AND NOT EXISTS (SELECT 1 FROM promoter_role_quality_revocation x WHERE x.review_id = r.id)
            ORDER BY r.created_at DESC LIMIT 1
        """, (config_hash, CLASSIFIER_VERSION))
        return cursor.fetchone() is not None


def revoke_quality_review(connection: Connection, review_id: int, reason: str) -> None:
    """Append a revocation; the DB requires active enforcement to be disabled first."""
    reason = reason.strip()
    if not reason or len(reason) > 500:
        raise ValueError("revocation reason must contain 1 to 500 characters")
    connection.execute("INSERT INTO promoter_role_quality_revocation (review_id, reason) VALUES (%s, %s)", (review_id, reason))
