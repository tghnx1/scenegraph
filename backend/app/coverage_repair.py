from __future__ import annotations

import subprocess
import time
from typing import Any, Callable

from app.coverage import CoverageOperations
from app.coverage_runs import CoverageRunStore, compact_error


TRANSIENT_REPAIR_ERRORS = (ConnectionError, TimeoutError, subprocess.TimeoutExpired)
TRANSIENT_PIPELINE_EXIT_CODES = {75}
TRANSIENT_AUDIT_ERROR_TYPES = {
    "ConnectionError",
    "OperationalError",
    "TimeoutError",
}


class CoverageRepairOrchestrator:
    def __init__(
        self,
        store: CoverageRunStore,
        *,
        operations_factory: Callable[..., CoverageOperations] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.store = store
        self.operations_factory = operations_factory or self._default_operations_factory
        self.sleep = sleep

    @staticmethod
    def _default_operations_factory(**kwargs: Any) -> CoverageOperations:
        return CoverageOperations(**kwargs)

    def _operations(self, run: dict[str, Any]) -> CoverageOperations:
        return self.operations_factory(
            min_date=str(run["min_date"]),
            max_date=str(run["max_date"]),
            apply=True,
        )

    @staticmethod
    def _date_rows(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {str(item["coverage_date"]): item for item in run["dates"]}

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        return float(min(30, 2 ** max(0, attempt - 1)))

    def _mark_run_failed(self, run_id: int, error: object, total_missing: int | None = None) -> None:
        self.store.update_run(
            run_id,
            status="failed",
            total_missing=total_missing,
            error=error,
            completed=True,
        )

    def _verify_with_retry(
        self,
        run: dict[str, Any],
        coverage_date: str,
        *,
        before_missing: int,
        max_attempts: int,
    ) -> dict[str, Any] | None:
        run_id = int(run["id"])
        latest = self._date_rows(self.store.get_run(run_id))[coverage_date]
        start_attempt = int(latest["verify_attempt_count"])
        for attempt in range(start_attempt + 1, max_attempts + 1):
            self.store.update_date(
                run_id,
                coverage_date,
                status="repairing",
                verify_status="running",
                verify_attempt_count=attempt,
                error=None,
                started=True,
            )
            verify_operations = self._operations(run)
            audit = verify_operations.audit_date(coverage_date)
            if audit["status"] != "audit_failed":
                status = "repaired" if before_missing > 0 and audit["missing_count"] == 0 else (
                    "still_missing" if audit["missing_count"] > 0 else "complete"
                )
                self.store.update_date(
                    run_id,
                    coverage_date,
                    status="complete" if audit["missing_count"] == 0 else "failed",
                    final_missing_count=audit["missing_count"],
                    final_audit=audit,
                    verify_status="succeeded" if audit["missing_count"] == 0 else "failed",
                    error=None if audit["missing_count"] == 0 else "StillMissingAfterBackfill",
                    completed=True,
                )
                return {"status": status, "audit": audit}

            error_type = str(audit.get("error_type") or "AuditError")
            retryable = error_type in TRANSIENT_AUDIT_ERROR_TYPES
            self.store.update_date(
                run_id,
                coverage_date,
                verify_status="failed",
                error=error_type,
            )
            if not retryable or attempt >= max_attempts:
                return None
            self.sleep(self._retry_delay(attempt))
        return None

    def _repair_date(
        self,
        run: dict[str, Any],
        coverage_date: str,
        initial_audit: dict[str, Any],
    ) -> bool:
        run_id = int(run["id"])
        max_attempts = int(run["max_attempts"])
        row = self._date_rows(self.store.get_run(run_id))[coverage_date]

        if row["backfill_status"] == "succeeded":
            verification = self._verify_with_retry(
                run,
                coverage_date,
                before_missing=int(initial_audit["missing_count"]),
                max_attempts=max_attempts,
            )
            return bool(verification and verification["audit"]["missing_count"] == 0)

        start_attempt = int(row["backfill_attempt_count"])
        for attempt in range(start_attempt + 1, max_attempts + 1):
            self.store.update_date(
                run_id,
                coverage_date,
                status="repairing",
                backfill_status="running",
                backfill_attempt_count=attempt,
                error=None,
                started=True,
            )
            attempt_operations = self._operations(run)
            current_audit = attempt_operations.audit_date(coverage_date)
            if current_audit["status"] == "audit_failed":
                error_type = str(current_audit.get("error_type") or "AuditError")
                self.store.update_date(
                    run_id,
                    coverage_date,
                    backfill_status="failed",
                    error=error_type,
                )
                if error_type not in TRANSIENT_AUDIT_ERROR_TYPES or attempt >= max_attempts:
                    return False
                self.sleep(self._retry_delay(attempt))
                continue
            if current_audit["missing_count"] == 0:
                self.store.update_date(
                    run_id,
                    coverage_date,
                    status="complete",
                    final_missing_count=0,
                    final_audit=current_audit,
                    backfill_status="skipped",
                    verify_status="skipped",
                    error=None,
                    completed=True,
                )
                return True
            try:
                attempt_operations.run_backfill(coverage_date)
            except TRANSIENT_REPAIR_ERRORS as exc:
                self.store.update_date(
                    run_id,
                    coverage_date,
                    backfill_status="failed",
                    error=exc,
                )
                if attempt >= max_attempts:
                    return False
                self.sleep(self._retry_delay(attempt))
                continue
            except subprocess.CalledProcessError as exc:
                if exc.returncode not in TRANSIENT_PIPELINE_EXIT_CODES:
                    self.store.update_date(
                        run_id,
                        coverage_date,
                        status="failed",
                        backfill_status="failed",
                        error=exc,
                        completed=True,
                    )
                    raise
                self.store.update_date(
                    run_id,
                    coverage_date,
                    backfill_status="failed",
                    error=exc,
                )
                if attempt >= max_attempts:
                    return False
                self.sleep(self._retry_delay(attempt))
                continue
            except Exception as exc:
                self.store.update_date(
                    run_id,
                    coverage_date,
                    status="failed",
                    backfill_status="failed",
                    error=exc,
                    completed=True,
                )
                raise

            self.store.update_date(
                run_id,
                coverage_date,
                backfill_status="succeeded",
                error=None,
            )
            verification = attempt_operations.verify_date(coverage_date)
            audit = verification["audit"]
            self.store.update_date(
                run_id,
                coverage_date,
                verify_attempt_count=1,
                verify_status="succeeded" if audit["missing_count"] == 0 else "failed",
                status="complete" if audit["missing_count"] == 0 else "failed",
                final_missing_count=audit["missing_count"],
                final_audit=audit,
                error=None if audit["missing_count"] == 0 else verification["status"],
                completed=True,
            )
            if audit["status"] == "audit_failed":
                verification_retry = self._verify_with_retry(
                    run,
                    coverage_date,
                    before_missing=int(initial_audit["missing_count"]),
                    max_attempts=max_attempts,
                )
                return bool(
                    verification_retry
                    and verification_retry["audit"]["missing_count"] == 0
                )
            return audit["missing_count"] == 0
        return False

    def run(self, run_id: int) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        self.store.update_run(run_id, status="running")
        operations = self._operations(run)
        try:
            initial = operations.audit_range(str(run["min_date"]), str(run["max_date"]))
            initial_by_date = {item["date"]: item for item in initial["dates"]}
            existing_rows = self._date_rows(run)
            for coverage_date, audit in initial_by_date.items():
                values: dict[str, Any] = {
                    "status": "audited",
                    "audit_status": audit["status"],
                    "initial_missing_count": audit["missing_count"],
                    "initial_audit": audit,
                    "error": audit.get("error_type"),
                    "started": True,
                }
                if audit["status"] in {"complete", "empty_on_ra"}:
                    existing = existing_rows[coverage_date]
                    existing_backfill = existing["backfill_status"]
                    completed_backfill = (
                        "skipped"
                        if existing_backfill == "pending"
                        else "succeeded"
                        if existing_backfill in {"running", "failed"}
                        else existing_backfill
                    )
                    values.update(
                        status="complete",
                        final_missing_count=0,
                        final_audit=audit,
                        backfill_status=completed_backfill,
                        verify_status=(
                            "skipped"
                            if completed_backfill == "skipped"
                            else "succeeded"
                            if existing["verify_status"] in {"pending", "running", "failed"}
                            else existing["verify_status"]
                        ),
                        error=None,
                        completed=True,
                    )
                self.store.update_date(run_id, coverage_date, **values)

            failed_audits = [
                item for item in initial["dates"] if item["status"] == "audit_failed"
            ]
            if failed_audits:
                error = f"InitialAuditFailed: {failed_audits[0]['date']} {failed_audits[0]['error_type']}"
                self._mark_run_failed(run_id, error)
                return self.store.get_run(run_id)

            missing_dates = [
                item for item in initial["dates"] if item["status"] == "missing_events"
            ]
            if len(missing_dates) > operations.config.max_backfills_per_run:
                raise RuntimeError("CoverageAgent backfill limit reached")

            for audit in missing_dates:
                repaired = self._repair_date(run, audit["date"], audit)
                if not repaired:
                    self.store.update_date(
                        run_id,
                        audit["date"],
                        status="failed",
                        error="RecoverableRepairAttemptsExhausted",
                        completed=True,
                    )

            final_operations = self._operations(run)
            final = final_operations.audit_range(str(run["min_date"]), str(run["max_date"]))
            final_by_date = {item["date"]: item for item in final["dates"]}
            for coverage_date, audit in final_by_date.items():
                self.store.update_date(
                    run_id,
                    coverage_date,
                    status="complete" if audit["status"] in {"complete", "empty_on_ra"} else "failed",
                    final_missing_count=audit["missing_count"],
                    final_audit=audit,
                    error=audit.get("error_type") if audit["status"] == "audit_failed" else (
                        None if audit["missing_count"] == 0 else "FinalAuditMissingEvents"
                    ),
                    completed=True,
                )

            converged = final["status"] == "complete" and final["total_missing"] == 0
            self.store.update_run(
                run_id,
                status="succeeded" if converged else "failed",
                total_missing=final["total_missing"],
                error=None if converged else "FinalCoverageAuditIncomplete",
                completed=True,
            )
            return self.store.get_run(run_id)
        except Exception as exc:
            self._mark_run_failed(run_id, compact_error(exc) or type(exc).__name__)
            return self.store.get_run(run_id)
