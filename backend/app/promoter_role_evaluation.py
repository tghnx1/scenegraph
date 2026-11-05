"""Quality gate for manually reviewed event-profile labels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["organizer", "venue", "both", "unknown"]


@dataclass(frozen=True, slots=True)
class ReviewedRole:
    actual_organizer: bool
    predicted_role: Role


@dataclass(frozen=True, slots=True)
class RoleQuality:
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int
    unknown: int
    precision: float | None
    recall: float | None
    passes: bool


def evaluate_roles(rows: tuple[ReviewedRole, ...]) -> RoleQuality:
    """Unknown counts as a miss for actual organizers; undefined metrics fail."""
    tp = sum(row.actual_organizer and row.predicted_role in {"organizer", "both"} for row in rows)
    fp = sum(not row.actual_organizer and row.predicted_role in {"organizer", "both"} for row in rows)
    tn = sum(not row.actual_organizer and row.predicted_role not in {"organizer", "both"} for row in rows)
    fn = sum(row.actual_organizer and row.predicted_role not in {"organizer", "both"} for row in rows)
    unknown = sum(row.predicted_role == "unknown" for row in rows)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    # A positive-only sample cannot measure how often venues are mistaken for organizers.
    passes = (precision is not None and recall is not None and fp + tn > 0
              and precision >= 0.7 and recall >= 0.7)
    return RoleQuality(tp, tn, fp, fn, unknown, precision, recall, passes)
