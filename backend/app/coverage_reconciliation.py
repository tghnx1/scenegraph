from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.coverage import fetch_db_event_ids
from app.coverage_reconciliation_runs import CoverageReconciliationStore
from app.coverage_runs import iter_dates
from app.event_dates import berlin_calendar_today, canonical_event_date, parse_calendar_date
from parsers.graphql_parser.event_listings import RAListingError, fetch_event_listings


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
TRANSIENT_PIPELINE_EXIT_CODES = {75}
TRANSIENT_PIPELINE_ERRORS = (ConnectionError, TimeoutError, subprocess.TimeoutExpired)


def _bounded_env_int(name: str, default: int, maximum: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


@dataclass(frozen=True)
class ReconciliationConfig:
    audit_chunk_days: int = 31
    pipeline_chunk_days: int = 7
    max_future_days: int = 365
    max_attempts: int = 3
    artifacts_dir: Path = Path("/tmp/scenegraph-reconciliation")

    @classmethod
    def from_env(cls) -> "ReconciliationConfig":
        return cls(
            audit_chunk_days=_bounded_env_int("RECONCILIATION_AUDIT_CHUNK_DAYS", 31, 31),
            pipeline_chunk_days=_bounded_env_int("RECONCILIATION_PIPELINE_CHUNK_DAYS", 7, 7),
            max_future_days=_bounded_env_int("RECONCILIATION_MAX_FUTURE_DAYS", 365, 3660),
            max_attempts=_bounded_env_int("RECONCILIATION_MAX_ATTEMPTS", 3, 5),
            artifacts_dir=Path(
                os.environ.get("RECONCILIATION_ARTIFACTS_DIR", "/tmp/scenegraph-reconciliation")
            ).expanduser().resolve(),
        )


class FutureHorizonExhausted(RuntimeError):
    pass


def date_chunks(min_date: date, max_date: date, days: int) -> Iterable[tuple[date, date]]:
    current = min_date
    while current <= max_date:
        end = min(max_date, current + timedelta(days=days - 1))
        yield current, end
        current = end + timedelta(days=1)


def contiguous_date_chunks(values: Iterable[date], days: int) -> list[tuple[date, date]]:
    ordered = sorted(set(values))
    chunks: list[tuple[date, date]] = []
    if not ordered:
        return chunks
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value != previous + timedelta(days=1) or (value - start).days >= days:
            chunks.append((start, previous))
            start = value
        previous = value
    chunks.append((start, previous))
    return chunks


class CoverageReconciliationOrchestrator:
    def __init__(
        self,
        store: CoverageReconciliationStore,
        *,
        listings_fetcher: Callable[[str, str], list[dict[str, str]]] = fetch_event_listings,
        db_fetcher: Callable[[str, str], set[str]] = fetch_db_event_ids,
        run_command: Callable[..., Any] = subprocess.run,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = berlin_calendar_today,
    ) -> None:
        self.store = store
        self.listings_fetcher = listings_fetcher
        self.db_fetcher = db_fetcher
        self.run_command = run_command
        self.sleep = sleep
        self.today = today

    @staticmethod
    def _delay(attempt: int) -> float:
        return float(min(30, 2 ** max(0, attempt - 1)))

    def _fetch_listings(self, min_date: date, max_date: date, max_attempts: int) -> list[dict[str, str]]:
        for attempt in range(1, max_attempts + 1):
            try:
                return self.listings_fetcher(min_date.isoformat(), max_date.isoformat())
            except RAListingError as exc:
                if not exc.retryable or attempt >= max_attempts:
                    raise
            except (ConnectionError, TimeoutError):
                if attempt >= max_attempts:
                    raise
            self.sleep(self._delay(attempt))
        raise AssertionError("listing retry loop ended unexpectedly")

    @staticmethod
    def _ids_by_date(
        listings: list[dict[str, str]], min_date: date, max_date: date
    ) -> dict[date, set[str]]:
        result: dict[date, set[str]] = {}
        for listing in listings:
            canonical = canonical_event_date(listing)
            if canonical is None or canonical < min_date or canonical > max_date:
                continue
            result.setdefault(canonical, set()).add(str(listing["id"]))
        return result

    def discover_max_date(self, run: dict[str, Any]) -> date:
        today = self.today()
        boundary = today + timedelta(days=int(run["future_horizon_days"]))
        maximum: date | None = None
        final_window_start = boundary - timedelta(days=int(run["audit_chunk_days"]) - 1)
        saw_event_in_final_window = False
        for start, end in date_chunks(today, boundary, int(run["audit_chunk_days"])):
            listings = self._fetch_listings(start, end, int(run["max_attempts"]))
            for listing in listings:
                canonical = canonical_event_date(listing)
                if canonical is None or canonical < today or canonical > boundary:
                    continue
                maximum = canonical if maximum is None else max(maximum, canonical)
                if canonical >= final_window_start:
                    saw_event_in_final_window = True
        if saw_event_in_final_window:
            raise FutureHorizonExhausted(
                f"RA events reached the configured future horizon ending {boundary.isoformat()}"
            )
        return max(today, maximum or today)

    def _audit_window(self, run: dict[str, Any], start: date, end: date) -> list[dict[str, Any]]:
        listings = self._fetch_listings(start, end, int(run["max_attempts"]))
        ra_by_date = self._ids_by_date(listings, start, end)
        audits: list[dict[str, Any]] = []
        current = start
        while current <= end:
            value = current.isoformat()
            ra_ids = set(ra_by_date.get(current, set()))
            db_ids = {str(item) for item in self.db_fetcher(self.store.database_url, value)}
            if not ra_ids and db_ids:
                confirmation = self._fetch_listings(current, current, int(run["max_attempts"]))
                ra_ids = self._ids_by_date(confirmation, current, current).get(current, set())
            missing = sorted(ra_ids - db_ids, key=lambda item: (len(item), item))
            extra = sorted(db_ids - ra_ids, key=lambda item: (len(item), item))
            if not ra_ids and db_ids:
                status = "ra_empty_conflict"
            elif not ra_ids:
                status = "empty_on_ra"
            elif missing:
                status = "missing_events"
            else:
                status = "complete"
            audits.append(
                {
                    "date": value,
                    "status": status,
                    "ra_count": len(ra_ids),
                    "db_count": len(db_ids),
                    "missing_count": len(missing),
                    "missing_event_ids": missing,
                    "extra_event_ids": extra,
                }
            )
            current += timedelta(days=1)
        return audits

    @staticmethod
    def _rows(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {str(item["coverage_date"]): item for item in run.get("dates", [])}

    def _current_audit(self, run: dict[str, Any]) -> dict[str, dict[str, Any]]:
        run_id = int(run["id"])
        min_date = run["requested_min_date"]
        max_date = run["resolved_max_date"]
        current_audits: dict[str, dict[str, Any]] = {}
        for start, end in date_chunks(min_date, max_date, int(run["audit_chunk_days"])):
            latest = self._rows(self.store.get_run(run_id))
            self.store.update_run(
                run_id, phase="planning_audit", current_min_date=start, current_max_date=end
            )
            for audit in self._audit_window(run, start, end):
                current_audits[audit["date"]] = audit
                row = latest[audit["date"]]
                values: dict[str, Any] = {
                    "status": "failed" if audit["status"] == "ra_empty_conflict" else "audited",
                    "final_audit_status": audit["status"],
                    "final_missing_count": audit["missing_count"],
                    "final_audit": audit,
                    "error": "RAEmptyConflict" if audit["status"] == "ra_empty_conflict" else None,
                }
                if row["initial_audit_status"] is None:
                    values.update(
                        initial_audit_status=audit["status"],
                        initial_missing_count=audit["missing_count"],
                        initial_audit=audit,
                    )
                self.store.update_date(
                    run_id,
                    audit["date"],
                    **values,
                )
        latest = self.store.get_run(run_id)
        if latest["initial_missing"] is None:
            total = sum(int(item["initial_missing_count"] or 0) for item in latest["dates"])
            self.store.update_run(run_id, initial_missing=total)
        return current_audits

    def _pipeline_command(self, run: dict[str, Any], start: date, end: date, *, refresh: bool) -> list[str]:
        command = [
            sys.executable,
            str(BACKEND_ROOT / "scripts" / "full_pipeline.py"),
            "--min-date", start.isoformat(),
            "--max-date", end.isoformat(),
            "--artifacts-dir", str(Path("/tmp/scenegraph-reconciliation") / f"run-{run['id']}"),
            "--skip-bio",
        ]
        if refresh:
            command.append("--no-dedup-with-db")
        return command

    def _run_pipeline_chunk(
        self, run: dict[str, Any], start: date, end: date, *, refresh: bool
    ) -> bool:
        run_id = int(run["id"])
        values = list(iter_dates(start, end))
        latest = self._rows(self.store.get_run(run_id))
        starting_attempt = max(int(latest[value.isoformat()]["pipeline_attempt_count"]) for value in values)
        command = self._pipeline_command(run, start, end, refresh=refresh)
        for local_attempt in range(1, int(run["max_attempts"]) + 1):
            attempt = starting_attempt + local_attempt
            for value in values:
                self.store.update_date(
                    run_id, value.isoformat(), status="processing", pipeline_status="running",
                    pipeline_attempt_count=attempt, error=None,
                )
            try:
                self.run_command(command, cwd=REPO_ROOT, check=True, shell=False)
            except TRANSIENT_PIPELINE_ERRORS as exc:
                retryable = True
                error: object = exc
            except subprocess.CalledProcessError as exc:
                retryable = exc.returncode in TRANSIENT_PIPELINE_EXIT_CODES
                error = exc
            except Exception:
                raise
            else:
                for value in values:
                    self.store.update_date(
                        run_id, value.isoformat(), pipeline_status="succeeded", error=None
                    )
                return True
            for value in values:
                self.store.update_date(
                    run_id, value.isoformat(), status="failed", pipeline_status="failed", error=error
                )
            if not retryable:
                raise error
            if local_attempt < int(run["max_attempts"]):
                self.sleep(self._delay(local_attempt))
        return False

    def _verify_chunk(self, run: dict[str, Any], start: date, end: date) -> bool:
        complete = True
        for audit in self._audit_window(run, start, end):
            healthy = audit["missing_count"] == 0 and audit["status"] != "ra_empty_conflict"
            self.store.update_date(
                int(run["id"]), audit["date"],
                status="complete" if healthy else "failed",
                final_audit_status=audit["status"], final_missing_count=audit["missing_count"],
                final_audit=audit, error=None if healthy else audit["status"], completed=healthy,
            )
            complete = complete and healthy
        return complete

    def _repair_historical(
        self,
        run: dict[str, Any],
        current_audits: dict[str, dict[str, Any]],
    ) -> bool:
        run_id = int(run["id"])
        rows = self.store.get_run(run_id)["dates"]
        missing_dates: list[date] = []
        all_complete = True
        for row in rows:
            if row["period"] != "historical":
                continue
            value = str(row["coverage_date"])
            audit = current_audits[value]
            if audit["status"] == "ra_empty_conflict":
                all_complete = False
                continue
            if int(audit["missing_count"]) == 0:
                if row["pipeline_status"] == "pending":
                    self.store.update_date(
                        run_id, value, status="complete", pipeline_status="skipped", completed=True
                    )
            else:
                missing_dates.append(row["coverage_date"])

        for start, end in contiguous_date_chunks(missing_dates, int(run["pipeline_chunk_days"])):
            self.store.update_run(
                run_id, phase="historical_repair", current_min_date=start, current_max_date=end
            )
            current = self._audit_window(run, start, end)
            still_missing = [parse_calendar_date(item["date"]) for item in current if item["missing_count"] > 0]
            if not still_missing:
                for item in current:
                    row = self._rows(self.store.get_run(run_id))[item["date"]]
                    self.store.update_date(
                        run_id, item["date"], status="complete",
                        pipeline_status=("skipped" if row["pipeline_status"] == "pending" else row["pipeline_status"]),
                        final_audit_status=item["status"], final_missing_count=0,
                        final_audit=item, error=None, completed=True,
                    )
                continue
            for child_start, child_end in contiguous_date_chunks(still_missing, int(run["pipeline_chunk_days"])):
                if not self._run_pipeline_chunk(run, child_start, child_end, refresh=False):
                    all_complete = False
                    continue
                all_complete = self._verify_chunk(run, child_start, child_end) and all_complete
        return all_complete

    def _refresh_future(
        self,
        run: dict[str, Any],
        current_audits: dict[str, dict[str, Any]],
        *,
        refresh_all: bool,
    ) -> bool:
        run_id = int(run["id"])
        rows = self.store.get_run(run_id)["dates"]
        pending = [
            row["coverage_date"] for row in rows
            if row["period"] == "future"
            and (
                int(current_audits[str(row["coverage_date"])]["missing_count"]) > 0
                or row["pipeline_status"] != "succeeded"
                or refresh_all
            )
        ]
        all_complete = True
        for start, end in contiguous_date_chunks(pending, int(run["pipeline_chunk_days"])):
            self.store.update_run(
                run_id, phase="future_refresh", current_min_date=start, current_max_date=end
            )
            if not self._run_pipeline_chunk(run, start, end, refresh=True):
                all_complete = False
                continue
            all_complete = self._verify_chunk(run, start, end) and all_complete
        return all_complete

    def _final_audit(self, run: dict[str, Any]) -> tuple[int, bool]:
        run_id = int(run["id"])
        total_missing = 0
        healthy = True
        for start, end in date_chunks(
            run["requested_min_date"], run["resolved_max_date"], int(run["audit_chunk_days"])
        ):
            self.store.update_run(run_id, phase="final_audit", current_min_date=start, current_max_date=end)
            for audit in self._audit_window(run, start, end):
                audit_healthy = audit["missing_count"] == 0 and audit["status"] != "ra_empty_conflict"
                self.store.update_date(
                    run_id, audit["date"], status="complete" if audit_healthy else "failed",
                    final_audit_status=audit["status"], final_missing_count=audit["missing_count"],
                    final_audit=audit, error=None if audit_healthy else audit["status"],
                    completed=audit_healthy,
                )
                total_missing += int(audit["missing_count"])
                healthy = healthy and audit_healthy
        return total_missing, healthy

    def run(self, run_id: int) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        try:
            if run["resolved_max_date"] is None:
                self.store.update_run(run_id, status="running", phase="discovering_horizon")
                if run["requested_max_date"] == "auto":
                    resolved = self.discover_max_date(run)
                else:
                    resolved = parse_calendar_date(str(run["requested_max_date"]))
                if run["requested_min_date"] > resolved:
                    raise ValueError("requested min_date cannot be later than resolved max_date")
                self.store.update_run(run_id, resolved_max_date=resolved)
                self.store.initialize_dates(
                    run_id, run["requested_min_date"], resolved, today=self.today()
                )
            run = self.store.get_run(run_id)
            refresh_all_future = run["initial_missing"] is None
            current_audits = self._current_audit(run)
            run = self.store.get_run(run_id)
            historical_ok = self._repair_historical(run, current_audits)
            run = self.store.get_run(run_id)
            future_ok = self._refresh_future(
                run,
                current_audits,
                refresh_all=refresh_all_future,
            )
            run = self.store.get_run(run_id)
            final_missing, audit_ok = self._final_audit(run)
            latest = self.store.get_run(run_id)
            future_complete = all(
                item["period"] != "future" or item["pipeline_status"] == "succeeded"
                for item in latest["dates"]
            )
            succeeded = historical_ok and future_ok and future_complete and audit_ok and final_missing == 0
            self.store.update_run(
                run_id, status="succeeded" if succeeded else "failed", phase="complete",
                current_min_date=None, current_max_date=None, final_missing=final_missing,
                error=None if succeeded else "FinalReconciliationIncomplete", completed=True,
            )
        except FutureHorizonExhausted as exc:
            self.store.update_run(
                run_id, status="future_horizon_exhausted", phase="discovering_horizon",
                error=exc, completed=True,
            )
        except BaseException as exc:
            if not isinstance(exc, (KeyboardInterrupt, SystemExit)):
                self.store.update_run(run_id, status="failed", error=exc, completed=True)
            raise
        return self.store.get_run(run_id)
