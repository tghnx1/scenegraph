from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

import psycopg
from psycopg.rows import dict_row

from app.ingestion_quarantine import fetch_unresolved_quarantine
from app.event_dates import event_in_date_range, parse_calendar_date
from app.quarantine import retry_quarantine_item


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
BERLIN_TIMEZONE = "Europe/Berlin"


def _positive_env_int(name: str, default: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be at least 1")
    return value


@dataclass(frozen=True)
class CoverageConfig:
    max_audit_days: int = 31
    max_backfills_per_run: int = 7
    quarantine_max_attempts: int = 3
    artifacts_dir: Path = Path("/tmp/scenegraph-coverage-agent")

    @classmethod
    def from_env(cls) -> "CoverageConfig":
        return cls(
            max_audit_days=_positive_env_int("COVERAGE_AGENT_MAX_AUDIT_DAYS", 31),
            max_backfills_per_run=_positive_env_int("COVERAGE_AGENT_MAX_BACKFILLS_PER_RUN", 7),
            quarantine_max_attempts=_positive_env_int("COVERAGE_AGENT_QUARANTINE_MAX_ATTEMPTS", 3),
            artifacts_dir=Path(
                os.environ.get("COVERAGE_AGENT_ARTIFACTS_DIR", "/tmp/scenegraph-coverage-agent")
            ).expanduser().resolve(),
        )


@dataclass(frozen=True)
class DateCoverageAudit:
    date: str
    ra_event_ids: list[str]
    db_event_ids: list[str]
    missing_event_ids: list[str]
    extra_event_ids: list[str]
    ra_count: int
    db_count: int
    missing_count: int
    status: str
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RangeCoverageAudit:
    min_date: str
    max_date: str
    dates: list[dict[str, Any]]
    incomplete_dates: list[str]
    total_missing: int
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_ra_listing_fetcher(min_date: str, max_date: str) -> set[str]:
    from parsers.graphql_parser.event_listings import fetch_event_listings

    return canonical_ra_event_ids(fetch_event_listings(min_date, max_date), min_date, max_date)


def canonical_ra_event_ids(
    listings: list[dict[str, str]],
    min_date: str,
    max_date: str,
) -> set[str]:
    return {
        str(listing["id"])
        for listing in listings
        if event_in_date_range(listing, min_date, max_date)
    }


def fetch_db_event_ids(database_url: str, audit_date: str) -> set[str]:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ra_event_id
                FROM events
                WHERE ra_event_id IS NOT NULL
                  AND (event_date AT TIME ZONE %s)::date = %s::date
                """,
                (BERLIN_TIMEZONE, audit_date),
            )
            return {str(row["ra_event_id"]) for row in cursor.fetchall()}


class CoverageOperations:
    def __init__(
        self,
        *,
        min_date: str,
        max_date: str,
        apply: bool = False,
        allow_quarantine_retry: bool = False,
        config: CoverageConfig | None = None,
        database_url: str | None = None,
        ra_fetcher: Callable[[str, str], set[str]] = default_ra_listing_fetcher,
        db_fetcher: Callable[[str, str], set[str]] = fetch_db_event_ids,
        run_command: Callable[..., Any] = subprocess.run,
        quarantine_fetcher: Callable[..., list[dict[str, Any]]] = fetch_unresolved_quarantine,
        quarantine_retry: Callable[..., None] = retry_quarantine_item,
    ) -> None:
        self.min_date = parse_calendar_date(min_date)
        self.max_date = parse_calendar_date(max_date)
        if self.min_date > self.max_date:
            raise ValueError("min_date cannot be later than max_date")
        self.config = config or CoverageConfig.from_env()
        self._validate_range(self.min_date, self.max_date)
        self.apply = apply
        self.allow_quarantine_retry = allow_quarantine_retry
        self.database_url = (database_url or os.environ.get("DATABASE_URL", "")).strip()
        if not self.database_url:
            raise RuntimeError("DATABASE_URL must be set")
        self.ra_fetcher = ra_fetcher
        self.db_fetcher = db_fetcher
        self.run_command = run_command
        self.quarantine_fetcher = quarantine_fetcher
        self.quarantine_retry = quarantine_retry
        self.audits: dict[str, DateCoverageAudit] = {}
        self.backfilled_dates: set[str] = set()
        self.retried_quarantine: set[tuple[str, int, str]] = set()
        self.actions: list[dict[str, Any]] = []

    def _validate_range(self, min_date: date, max_date: date) -> None:
        days = (max_date - min_date).days + 1
        if days > self.config.max_audit_days:
            raise ValueError(
                f"Audit range is {days} days; maximum is {self.config.max_audit_days}"
            )

    def _require_requested_date(self, value: str) -> date:
        parsed = parse_calendar_date(value)
        if parsed < self.min_date or parsed > self.max_date:
            raise ValueError(f"Date {value} is outside the requested audit range")
        return parsed

    def _perform_audit(self, value: str) -> DateCoverageAudit:
        try:
            ra_ids = {str(event_id) for event_id in self.ra_fetcher(value, value)}
            db_ids = {str(event_id) for event_id in self.db_fetcher(self.database_url, value)}
        except Exception as exc:
            return DateCoverageAudit(
                date=value,
                ra_event_ids=[],
                db_event_ids=[],
                missing_event_ids=[],
                extra_event_ids=[],
                ra_count=0,
                db_count=0,
                missing_count=0,
                status="audit_failed",
                error_type=type(exc).__name__,
            )

        missing = sorted(ra_ids - db_ids, key=lambda item: (len(item), item))
        extra = sorted(db_ids - ra_ids, key=lambda item: (len(item), item))
        status = "empty_on_ra" if not ra_ids else "missing_events" if missing else "complete"
        return DateCoverageAudit(
            date=value,
            ra_event_ids=sorted(ra_ids, key=lambda item: (len(item), item)),
            db_event_ids=sorted(db_ids, key=lambda item: (len(item), item)),
            missing_event_ids=missing,
            extra_event_ids=extra,
            ra_count=len(ra_ids),
            db_count=len(db_ids),
            missing_count=len(missing),
            status=status,
        )

    def audit_date(self, date: str) -> dict[str, Any]:
        self._require_requested_date(date)
        audit = self._perform_audit(date)
        self.audits[date] = audit
        self.actions.append(
            {"action": "audit_date", "date": date, "status": audit.status, "missing_count": audit.missing_count}
        )
        return audit.to_dict()

    def audit_range(self, min_date: str, max_date: str) -> dict[str, Any]:
        start = self._require_requested_date(min_date)
        end = self._require_requested_date(max_date)
        if start > end:
            raise ValueError("min_date cannot be later than max_date")
        self._validate_range(start, end)
        audits: list[dict[str, Any]] = []
        current = start
        while current <= end:
            audit = self.audit_date(current.isoformat())
            audits.append(
                {
                    "date": audit["date"],
                    "ra_count": audit["ra_count"],
                    "db_count": audit["db_count"],
                    "missing_count": audit["missing_count"],
                    "missing_event_ids": audit["missing_event_ids"],
                    "status": audit["status"],
                    "error_type": audit["error_type"],
                }
            )
            current += timedelta(days=1)
        incomplete = [item["date"] for item in audits if item["status"] in {"missing_events", "audit_failed"}]
        result = RangeCoverageAudit(
            min_date=min_date,
            max_date=max_date,
            dates=audits,
            incomplete_dates=incomplete,
            total_missing=sum(int(item["missing_count"]) for item in audits),
            status="incomplete" if incomplete else "complete",
        )
        return result.to_dict()

    def run_backfill(self, date: str) -> dict[str, Any]:
        self._require_requested_date(date)
        if not self.apply:
            raise PermissionError("Backfill requires --apply")
        audit = self.audits.get(date)
        if audit is None:
            raise RuntimeError("Date must be audited before backfill")
        if audit.status != "missing_events" or audit.missing_count < 1:
            raise RuntimeError("Backfill is allowed only for an audited date with missing events")
        if date in self.backfilled_dates:
            raise RuntimeError(f"Date {date} has already been backfilled in this invocation")
        if len(self.backfilled_dates) >= self.config.max_backfills_per_run:
            raise RuntimeError("CoverageAgent backfill limit reached")

        command = [
            sys.executable,
            str(BACKEND_ROOT / "scripts" / "full_pipeline.py"),
            "--min-date",
            date,
            "--max-date",
            date,
            "--artifacts-dir",
            str(self.config.artifacts_dir),
            "--skip-bio",
        ]
        self.backfilled_dates.add(date)
        self.actions.append({"action": "run_backfill", "date": date, "status": "started"})
        try:
            self.run_command(command, cwd=REPO_ROOT, check=True, shell=False)
        except BaseException as exc:
            self.actions.append(
                {
                    "action": "run_backfill",
                    "date": date,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                }
            )
            raise
        result = {"date": date, "exit_code": 0, "status": "succeeded"}
        self.actions.append({"action": "run_backfill", **result})
        return result

    def verify_date(self, date: str) -> dict[str, Any]:
        self._require_requested_date(date)
        before = self.audits.get(date)
        if before is None:
            raise RuntimeError("Date must be audited before verification")
        after = self._perform_audit(date)
        self.audits[date] = after
        if after.status == "audit_failed":
            status = "verification_failed"
        elif before.missing_count > 0 and after.missing_count == 0:
            status = "repaired"
        elif after.missing_count > 0:
            status = "still_missing"
        else:
            status = "complete"
        result = {
            "date": date,
            "before_missing": before.missing_count,
            "after_missing": after.missing_count,
            "status": status,
            "audit": after.to_dict(),
        }
        self.actions.append(
            {
                "action": "verify_date",
                **{
                    key: result[key]
                    for key in ("date", "before_missing", "after_missing", "status")
                },
            }
        )
        return result

    def quarantine_status(
        self,
        entity_type: str | None = None,
        stage: str | None = None,
        entity_id: int | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")
        items = self.quarantine_fetcher(
            self.database_url,
            entity_type=entity_type,
            stage=stage,
            entity_id=entity_id,
            limit=limit,
        )
        compact = [
            {
                "entity_type": str(item["entity_type"]),
                "entity_id": int(item["entity_id"]),
                "stage": str(item["stage"]),
                "error_type": str(item["error_type"]),
                "attempt_count": int(item["attempt_count"]),
            }
            for item in items
        ]
        result = {
            "total": len(compact),
            "events": sum(item["entity_type"] == "event" for item in compact),
            "artists": sum(item["entity_type"] == "artist" for item in compact),
            "items": compact,
        }
        self.actions.append({"action": "quarantine_status", "total": result["total"]})
        return result

    def retry_quarantine(self, entity_type: str, entity_id: int, stage: str) -> dict[str, Any]:
        if not self.apply or not self.allow_quarantine_retry:
            raise PermissionError("Quarantine retry requires --apply and --retry-quarantine")
        key = (entity_type, entity_id, stage)
        if key in self.retried_quarantine:
            raise RuntimeError("Quarantine item has already been retried in this invocation")
        status = self.quarantine_status(entity_type, stage, entity_id, limit=1)
        if not status["items"]:
            raise RuntimeError("Unresolved quarantine item not found")
        item = status["items"][0]
        if item["attempt_count"] >= self.config.quarantine_max_attempts:
            raise RuntimeError("Quarantine item is at or above the automatic retry limit")
        self.retried_quarantine.add(key)
        self.quarantine_retry(entity_type, entity_id, stage)
        remaining = self.quarantine_fetcher(
            self.database_url,
            entity_type=entity_type,
            stage=stage,
            entity_id=entity_id,
            limit=1,
        )
        retry_status = "still_quarantined" if remaining else "resolved"
        result = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "stage": stage,
            "status": retry_status,
        }
        if remaining:
            result["attempt_count"] = int(remaining[0]["attempt_count"])
        self.actions.append({"action": "retry_quarantine", **result})
        return result

    def report(self) -> dict[str, Any]:
        return {
            "min_date": self.min_date.isoformat(),
            "max_date": self.max_date.isoformat(),
            "apply": self.apply,
            "audited_dates": sorted(self.audits),
            "coverage": [self.audits[value].to_dict() for value in sorted(self.audits)],
            "proposed_repair_dates": sorted(
                value for value, audit in self.audits.items() if audit.status == "missing_events"
            ),
            "backfilled_dates": sorted(self.backfilled_dates),
            "actions": list(self.actions),
        }
