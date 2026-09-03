from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.coverage_reconciliation import (
    CoverageReconciliationOrchestrator,
    ReconciliationConfig,
)
from app.coverage_reconciliation_runs import CoverageReconciliationStore
from app.event_dates import shift_calendar_months


BERLIN_TIMEZONE_NAME = "Europe/Berlin"
BERLIN_TIMEZONE = ZoneInfo(BERLIN_TIMEZONE_NAME)
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
DEFAULT_ARTIFACTS_DIR = Path("/tmp/scenegraph-import-runs")


class DailyIngestionBusyError(RuntimeError):
    pass


class DailyCoverageError(RuntimeError):
    pass


def resolve_target_date(
    *,
    now: datetime | None = None,
    environ: Mapping[str, str] | None = None,
) -> date:
    environment = os.environ if environ is None else environ
    override = environment.get("DAILY_INGEST_DATE", "").strip()
    if override:
        try:
            parsed = date.fromisoformat(override)
        except ValueError as exc:
            raise ValueError(
                "DAILY_INGEST_DATE must use a valid YYYY-MM-DD calendar date"
            ) from exc
        if parsed.isoformat() != override:
            raise ValueError("DAILY_INGEST_DATE must use exact YYYY-MM-DD format")
        return parsed

    current = now or datetime.now(tz=BERLIN_TIMEZONE)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return current.astimezone(BERLIN_TIMEZONE).date()


def daily_date_ranges(reference_date: date) -> dict[str, date]:
    return {
        "coverage_min": shift_calendar_months(reference_date, -3),
        "coverage_max": shift_calendar_months(reference_date, 3),
        "refresh_min": reference_date,
        "refresh_max": shift_calendar_months(reference_date, 1),
    }


def build_pipeline_command(min_date: date, max_date: date, artifacts_dir: Path) -> list[str]:
    return [
        sys.executable,
        str(BACKEND_ROOT / "scripts" / "full_pipeline.py"),
        "--min-date",
        min_date.isoformat(),
        "--max-date",
        max_date.isoformat(),
        "--artifacts-dir",
        str(artifacts_dir),
        "--skip-bio",
        "--no-dedup-with-db",
    ]


def _print_coverage_summary(run: Mapping[str, object]) -> None:
    audits = [
        row.get("final_audit")
        for row in run.get("dates", [])
        if isinstance(row, Mapping) and isinstance(row.get("final_audit"), Mapping)
    ]
    ra_events = sum(int(audit.get("ra_count", 0)) for audit in audits)
    db_events = sum(int(audit.get("db_count", 0)) for audit in audits)
    extras = sum(len(audit.get("extra_event_ids", [])) for audit in audits)
    unresolvable = sum(int(audit.get("source_unresolvable_count", 0)) for audit in audits)
    initial_missing = int(run.get("initial_missing") or 0)
    final_missing = int(run.get("final_missing") or 0)
    repaired = max(0, initial_missing - final_missing)
    print(
        "Coverage reconciliation summary: "
        f"ra_events={ra_events}; db_events={db_events}; "
        f"missing={initial_missing}; final_missing={final_missing}; "
        f"extra={extras}; repaired={repaired}; "
        f"source_unresolvable={unresolvable}"
    )


def run_daily_ingestion(
    *,
    target_date: date | None = None,
    environ: Mapping[str, str] | None = None,
    run_command: Callable[..., subprocess.CompletedProcess[object]] = subprocess.run,
    store_factory: Callable[[str], CoverageReconciliationStore] = CoverageReconciliationStore,
    orchestrator_factory: Callable[..., CoverageReconciliationOrchestrator] = (
        CoverageReconciliationOrchestrator
    ),
) -> int:
    environment = os.environ if environ is None else environ
    reference_date = target_date or resolve_target_date(environ=environment)
    ranges = daily_date_ranges(reference_date)
    artifacts_dir = Path(
        environment.get("DAILY_INGEST_ARTIFACTS_DIR", str(DEFAULT_ARTIFACTS_DIR))
    ).expanduser()
    database_url = environment.get("DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("DATABASE_URL must be set")
    config = ReconciliationConfig.from_env(environment)
    store = store_factory(database_url)
    worker_lock = store.acquire_worker_lock()
    if worker_lock is None:
        raise DailyIngestionBusyError("coverage reconciliation worker lock is busy")

    try:
        print(f"Daily ingestion date: {reference_date.isoformat()}")
        print(f"Target timezone: {BERLIN_TIMEZONE_NAME}")
        print("Coverage reconciliation:")
        print(f"  min: {ranges['coverage_min'].isoformat()}")
        print(f"  max: {ranges['coverage_max'].isoformat()}")
        reconciliation = store.enqueue(
            min_date=ranges["coverage_min"],
            requested_max_date=ranges["coverage_max"].isoformat(),
            future_horizon_days=config.max_future_days,
            audit_chunk_days=config.audit_chunk_days,
            pipeline_chunk_days=config.pipeline_chunk_days,
            max_attempts=config.max_attempts,
            source_quarantine_ttl_days=config.source_quarantine_ttl_days,
            refresh_all_future=False,
        )
        run_id = int(reconciliation["id"])
        store.update_run(
            run_id,
            status="running",
            worker_id=f"daily-ingestion:{os.getpid()}",
        )
        coverage_result = orchestrator_factory(
            store,
            today=lambda: reference_date,
        ).run(run_id)
        _print_coverage_summary(coverage_result)
        if coverage_result["status"] != "succeeded":
            raise DailyCoverageError(
                f"coverage reconciliation {run_id} finished with "
                f"status={coverage_result['status']}"
            )

        print("Forced event refresh:")
        print(f"  min: {ranges['refresh_min'].isoformat()}")
        print(f"  max: {ranges['refresh_max'].isoformat()}")
        run_command(
            build_pipeline_command(
                ranges["refresh_min"],
                ranges["refresh_max"],
                artifacts_dir,
            ),
            cwd=REPO_ROOT,
            check=True,
        )
        print("Forced event refresh: succeeded")

        print("Recommendation scheduler: started")
        run_command(
            [sys.executable, "-m", "app.recommendations.scheduler"],
            cwd=BACKEND_ROOT,
            check=True,
        )
        print("Recommendation scheduler: succeeded")
        return 0
    finally:
        store.release_worker_lock(worker_lock)


def main() -> int:
    try:
        return run_daily_ingestion()
    except ValueError as exc:
        print(f"Daily ingestion configuration error: {exc}", file=sys.stderr)
        return 2
    except DailyIngestionBusyError as exc:
        print(f"Daily ingestion temporarily unavailable: {exc}", file=sys.stderr)
        return 75
    except DailyCoverageError as exc:
        print(f"Daily ingestion failed: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(
            f"Daily ingestion failed; command exited with code {exc.returncode}",
            file=sys.stderr,
        )
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
