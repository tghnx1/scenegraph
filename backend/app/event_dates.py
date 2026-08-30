from __future__ import annotations

from datetime import date
from typing import Any, Mapping


def parse_calendar_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid YYYY-MM-DD date: {value}") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"Invalid YYYY-MM-DD date: {value}")
    return parsed


def canonical_event_date(event: Mapping[str, Any]) -> date | None:
    raw_date = str(event.get("date") or "").strip()
    candidate = raw_date[:10]
    if len(candidate) != 10:
        return None
    try:
        return parse_calendar_date(candidate)
    except ValueError:
        return None


def event_in_date_range(
    event: Mapping[str, Any],
    min_date: str,
    max_date: str,
) -> bool:
    event_date = canonical_event_date(event)
    if event_date is None:
        return False
    return parse_calendar_date(min_date) <= event_date <= parse_calendar_date(max_date)
