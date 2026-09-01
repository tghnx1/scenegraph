from __future__ import annotations

import copy
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.coverage import CoverageConfig, CoverageOperations
from app.coverage_repair import CoverageRepairOrchestrator
from app.coverage_runs import compact_error
from app.coverage_worker import process_next_run


DATE_1 = "2026-08-20"
DATE_2 = "2026-08-21"


class MemoryCoverageStore:
    def __init__(self, min_date=DATE_1, max_date=DATE_2, *, max_attempts=3):
        now = datetime.now(timezone.utc)
        self.run = {
            "id": 1,
            "min_date": date.fromisoformat(min_date),
            "max_date": date.fromisoformat(max_date),
            "status": "queued",
            "max_attempts": max_attempts,
            "total_missing": None,
            "worker_id": None,
            "error": None,
            "started_at": None,
            "completed_at": None,
            "created_at": now,
            "updated_at": now,
            "dates": [],
        }
        current = date.fromisoformat(min_date)
        end = date.fromisoformat(max_date)
        while current <= end:
            self.run["dates"].append(
                {
                    "coverage_run_id": 1,
                    "coverage_date": current,
                    "status": "pending",
                    "initial_missing_count": None,
                    "final_missing_count": None,
                    "audit_status": None,
                    "backfill_status": "pending",
                    "backfill_attempt_count": 0,
                    "verify_status": "pending",
                    "verify_attempt_count": 0,
                    "initial_audit": None,
                    "final_audit": None,
                    "error": None,
                    "started_at": None,
                    "completed_at": None,
                }
            )
            current = current.fromordinal(current.toordinal() + 1)
        self.claimed = False

    def get_run(self, run_id):
        assert run_id == 1
        return copy.deepcopy(self.run)

    def update_run(self, run_id, **values):
        assert run_id == 1
        completed = values.pop("completed", False)
        self.run.update(values)
        if completed:
            self.run["completed_at"] = datetime.now(timezone.utc)

    def update_date(self, run_id, coverage_date, **values):
        assert run_id == 1
        row = next(
            item for item in self.run["dates"] if str(item["coverage_date"]) == coverage_date
        )
        started = values.pop("started", False)
        completed = values.pop("completed", False)
        row.update(values)
        if started and row["started_at"] is None:
            row["started_at"] = datetime.now(timezone.utc)
        if completed:
            row["completed_at"] = datetime.now(timezone.utc)

    def claim_next(self, worker_id):
        if self.claimed:
            return None
        self.claimed = True
        self.run["status"] = "running"
        self.run["worker_id"] = worker_id
        return self.get_run(1)


def operations_factory(db_by_date, run_command, *, ra_by_date=None, max_backfills=7):
    ra_by_date = ra_by_date or {DATE_1: {"1"}, DATE_2: {"1"}}

    def factory(**kwargs):
        return CoverageOperations(
            **kwargs,
            config=CoverageConfig(max_backfills_per_run=max_backfills),
            database_url="postgresql://test/scenegraph",
            ra_fetcher=lambda start, _end: set(ra_by_date[start]),
            db_fetcher=lambda _url, audit_date: set(db_by_date[audit_date]),
            run_command=run_command,
            quarantine_fetcher=lambda *_args, **_kwargs: [],
            source_quarantine_fetcher=lambda *_args, **_kwargs: set(),
        )

    return factory


def command_date(command):
    return command[command.index("--min-date") + 1]


def test_interrupted_run_resumes_remaining_date_without_repeating_completed_date():
    store = MemoryCoverageStore()
    db = {DATE_1: set(), DATE_2: set()}
    calls = []
    interrupted = True

    def run_command(command, **_kwargs):
        nonlocal interrupted
        coverage_date = command_date(command)
        calls.append(coverage_date)
        if coverage_date == DATE_2 and interrupted:
            interrupted = False
            raise KeyboardInterrupt("worker terminated")
        db[coverage_date].add("1")

    orchestrator = CoverageRepairOrchestrator(
        store,
        operations_factory=operations_factory(db, run_command),
        sleep=lambda _seconds: None,
    )

    with pytest.raises(KeyboardInterrupt):
        orchestrator.run(1)

    partial = store.get_run(1)
    first, second = partial["dates"]
    assert first["status"] == "complete"
    assert first["backfill_status"] == "succeeded"
    assert second["backfill_status"] == "running"

    result = orchestrator.run(1)

    assert result["status"] == "succeeded"
    assert result["total_missing"] == 0
    assert calls == [DATE_1, DATE_2, DATE_2]
    assert result["dates"][0]["backfill_attempt_count"] == 1
    assert result["dates"][1]["backfill_attempt_count"] == 2


def test_resume_reaudits_before_repeating_an_ambiguous_running_backfill():
    store = MemoryCoverageStore(min_date=DATE_1, max_date=DATE_1)
    db = {DATE_1: set()}
    calls = []
    interrupted = True

    def run_command(command, **_kwargs):
        nonlocal interrupted
        calls.append(command_date(command))
        db[DATE_1].add("1")
        if interrupted:
            interrupted = False
            raise KeyboardInterrupt("worker stopped after child completed")

    orchestrator = CoverageRepairOrchestrator(
        store,
        operations_factory=operations_factory(
            db,
            run_command,
            ra_by_date={DATE_1: {"1"}},
        ),
    )

    with pytest.raises(KeyboardInterrupt):
        orchestrator.run(1)

    result = orchestrator.run(1)

    assert result["status"] == "succeeded"
    assert calls == [DATE_1]
    assert result["dates"][0]["backfill_status"] == "succeeded"
    assert result["dates"][0]["verify_status"] == "succeeded"


def test_zero_missing_range_performs_no_backfill_and_final_audit_is_required():
    store = MemoryCoverageStore()
    db = {DATE_1: {"1"}, DATE_2: {"1"}}
    calls = []
    factory_calls = 0
    base_factory = operations_factory(db, lambda command, **_kwargs: calls.append(command))

    def counting_factory(**kwargs):
        nonlocal factory_calls
        factory_calls += 1
        return base_factory(**kwargs)

    result = CoverageRepairOrchestrator(store, operations_factory=counting_factory).run(1)

    assert result["status"] == "succeeded"
    assert result["total_missing"] == 0
    assert calls == []
    assert factory_calls == 2  # Initial and mandatory final full-range audits.
    assert all(item["backfill_status"] == "skipped" for item in result["dates"])


def test_final_range_audit_blocks_success_when_gap_reappears():
    store = MemoryCoverageStore(min_date=DATE_1, max_date=DATE_1)
    db_results = iter((set(), set(), {"1"}, set()))
    fetch_count = 0

    def factory(**kwargs):
        def db_fetcher(_url, _audit_date):
            nonlocal fetch_count
            fetch_count += 1
            return next(db_results)

        return CoverageOperations(
            **kwargs,
            database_url="postgresql://test/scenegraph",
            ra_fetcher=lambda *_args: {"1"},
            db_fetcher=db_fetcher,
            run_command=lambda *_args, **_kwargs: None,
            quarantine_fetcher=lambda *_args, **_kwargs: [],
            source_quarantine_fetcher=lambda *_args, **_kwargs: set(),
        )

    result = CoverageRepairOrchestrator(store, operations_factory=factory).run(1)

    assert fetch_count == 4
    assert result["status"] == "failed"
    assert result["total_missing"] == 1
    assert result["error"] == "FinalCoverageAuditIncomplete"


def test_transient_failure_retries_only_same_date_within_limit():
    store = MemoryCoverageStore(min_date=DATE_1, max_date=DATE_1, max_attempts=2)
    db = {DATE_1: set()}
    calls = []

    def run_command(command, **_kwargs):
        calls.append(command_date(command))
        if len(calls) == 1:
            raise TimeoutError("temporary runner timeout")
        db[DATE_1].add("1")

    result = CoverageRepairOrchestrator(
        store,
        operations_factory=operations_factory(
            db,
            run_command,
            ra_by_date={DATE_1: {"1"}},
        ),
        sleep=lambda _seconds: None,
    ).run(1)

    assert result["status"] == "succeeded"
    assert calls == [DATE_1, DATE_1]
    assert result["dates"][0]["backfill_attempt_count"] == 2


def test_pipeline_lock_contention_exit_is_retried_but_other_exit_codes_are_not():
    store = MemoryCoverageStore(min_date=DATE_1, max_date=DATE_1, max_attempts=2)
    db = {DATE_1: set()}
    calls = []

    def run_command(command, **_kwargs):
        calls.append(command_date(command))
        if len(calls) == 1:
            raise subprocess.CalledProcessError(75, command)
        db[DATE_1].add("1")

    result = CoverageRepairOrchestrator(
        store,
        operations_factory=operations_factory(
            db,
            run_command,
            ra_by_date={DATE_1: {"1"}},
        ),
        sleep=lambda _seconds: None,
    ).run(1)

    assert result["status"] == "succeeded"
    assert calls == [DATE_1, DATE_1]


def test_non_retryable_failure_marks_run_failed_and_stops():
    store = MemoryCoverageStore()
    db = {DATE_1: set(), DATE_2: set()}
    calls = []

    def run_command(command, **_kwargs):
        calls.append(command_date(command))
        raise subprocess.CalledProcessError(2, command)

    result = CoverageRepairOrchestrator(
        store,
        operations_factory=operations_factory(db, run_command),
        sleep=lambda _seconds: None,
    ).run(1)

    assert result["status"] == "failed"
    assert calls == [DATE_1]
    assert result["dates"][0]["backfill_attempt_count"] == 1
    assert result["dates"][1]["backfill_attempt_count"] == 0


def test_exhausted_transient_date_keeps_progress_and_continues_next_date():
    store = MemoryCoverageStore(max_attempts=2)
    db = {DATE_1: set(), DATE_2: set()}
    calls = []

    def run_command(command, **_kwargs):
        coverage_date = command_date(command)
        calls.append(coverage_date)
        if coverage_date == DATE_1:
            raise TimeoutError("temporary failure persisted")
        db[coverage_date].add("1")

    result = CoverageRepairOrchestrator(
        store,
        operations_factory=operations_factory(db, run_command),
        sleep=lambda _seconds: None,
    ).run(1)

    assert calls == [DATE_1, DATE_1, DATE_2]
    assert result["status"] == "failed"
    assert result["total_missing"] == 1
    assert result["dates"][0]["status"] == "failed"
    assert result["dates"][1]["status"] == "complete"


def test_orchestrator_preserves_existing_backfill_limit():
    store = MemoryCoverageStore()
    db = {DATE_1: set(), DATE_2: set()}
    calls = []

    result = CoverageRepairOrchestrator(
        store,
        operations_factory=operations_factory(
            db,
            lambda command, **_kwargs: calls.append(command),
            max_backfills=1,
        ),
    ).run(1)

    assert result["status"] == "failed"
    assert "backfill limit reached" in result["error"]
    assert calls == []


def test_quarantine_is_not_part_of_coverage_repair():
    store = MemoryCoverageStore(min_date=DATE_1, max_date=DATE_1)
    db = {DATE_1: {"1"}}
    quarantine_calls = []

    def factory(**kwargs):
        return CoverageOperations(
            **kwargs,
            database_url="postgresql://test/scenegraph",
            ra_fetcher=lambda *_args: {"1"},
            db_fetcher=lambda *_args: db[DATE_1],
            run_command=lambda *_args, **_kwargs: pytest.fail("no backfill expected"),
            quarantine_fetcher=lambda *_args, **_kwargs: quarantine_calls.append(True),
            source_quarantine_fetcher=lambda *_args, **_kwargs: set(),
        )

    result = CoverageRepairOrchestrator(store, operations_factory=factory).run(1)

    assert result["status"] == "succeeded"
    assert quarantine_calls == []


def test_worker_processes_persisted_run_independently_of_launcher():
    store = MemoryCoverageStore(min_date=DATE_1, max_date=DATE_1)
    processed = []

    class FakeOrchestrator:
        def __init__(self, received_store):
            assert received_store is store

        def run(self, run_id):
            processed.append(run_id)
            store.update_run(run_id, status="succeeded", total_missing=0, completed=True)
            return store.get_run(run_id)

    assert process_next_run(
        store,
        worker_id="coverage-worker-test",
        orchestrator_factory=FakeOrchestrator,
    ) is True
    assert processed == [1]
    assert store.run["worker_id"] == "coverage-worker-test"
    assert process_next_run(
        store,
        worker_id="coverage-worker-test",
        orchestrator_factory=FakeOrchestrator,
    ) is False


def test_production_worker_has_fixed_non_shell_command():
    compose = (Path(__file__).resolve().parents[2] / "docker-compose.prod.yml").read_text()

    assert 'coverage-worker:' in compose
    assert 'command: ["python", "-m", "app.coverage_worker"]' in compose


def test_persisted_errors_are_bounded_and_redact_credentials(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "super-secret-provider-key")

    result = compact_error(RuntimeError("failed with super-secret-provider-key" + "x" * 2000))

    assert "super-secret-provider-key" not in result
    assert "[redacted]" in result
    assert len(result) <= 1000
