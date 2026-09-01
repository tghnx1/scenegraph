from __future__ import annotations

import copy
import json
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import coverage_reconcile
from app.coverage_reconcile_worker import process_next_reconciliation
from app.coverage_reconciliation import (
    CoverageReconciliationOrchestrator,
    FutureHorizonExhausted,
    contiguous_date_chunks,
    date_chunks,
)
from app.coverage_reconciliation_runs import public_reconciliation_status
from app.coverage_runs import iter_dates
from app.event_dates import berlin_calendar_today
from parsers.graphql_parser.event_listings import RAListingError


TODAY = date(2026, 8, 30)


class MemoryReconciliationStore:
    database_url = "postgresql://test/scenegraph"

    def __init__(self, min_date: date, max_date: date | None, *, requested_max: str | None = None):
        now = datetime.now(timezone.utc)
        self.run = {
            "id": 1,
            "requested_min_date": min_date,
            "requested_max_date": requested_max or max_date.isoformat(),
            "resolved_max_date": max_date,
            "future_horizon_days": 365,
            "audit_chunk_days": 31,
            "pipeline_chunk_days": 7,
            "max_attempts": 3,
            "source_quarantine_ttl_days": 7,
            "status": "queued",
            "phase": "pending",
            "current_min_date": None,
            "current_max_date": None,
            "initial_missing": None,
            "final_missing": None,
            "worker_id": None,
            "error": None,
            "started_at": None,
            "completed_at": None,
            "created_at": now,
            "updated_at": now,
            "dates": [],
        }
        if max_date is not None:
            self.initialize_dates(1, min_date, max_date, today=TODAY)
        self.claimed = False

    def initialize_dates(self, run_id, min_date, max_date, *, today):
        assert run_id == 1
        existing = {row["coverage_date"] for row in self.run["dates"]}
        for value in iter_dates(min_date, max_date):
            if value in existing:
                continue
            self.run["dates"].append(
                {
                    "coverage_date": value,
                    "period": "historical" if value < today else "future",
                    "status": "pending",
                    "initial_audit_status": None,
                    "initial_missing_count": None,
                    "pipeline_status": "pending",
                    "pipeline_attempt_count": 0,
                    "final_audit_status": None,
                    "final_missing_count": None,
                    "initial_audit": None,
                    "final_audit": None,
                    "error": None,
                    "started_at": None,
                    "completed_at": None,
                }
            )

    def get_run(self, run_id):
        assert run_id == 1
        return copy.deepcopy(self.run)

    def get_latest(self):
        return self.get_run(1)

    def update_run(self, run_id, *, completed=False, **values):
        assert run_id == 1
        self.run.update(values)
        if completed:
            self.run["completed_at"] = datetime.now(timezone.utc)

    def update_date(self, run_id, coverage_date, *, completed=False, **values):
        assert run_id == 1
        row = next(item for item in self.run["dates"] if str(item["coverage_date"]) == coverage_date)
        row.update(values)
        if values.get("status") == "processing" and row["started_at"] is None:
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


def listing_fetcher(expected, calls=None):
    def fetch(start, end):
        if calls is not None:
            calls.append((start, end))
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
        return [
            {"id": event_id, "date": f"{value.isoformat()}T20:00:00Z"}
            for value in iter_dates(start_date, end_date)
            for event_id in sorted(expected.get(value, set()))
        ]

    return fetch


def pipeline_runner(expected, db, calls, *, interrupt_after=None, fail=None):
    def run(command, **kwargs):
        assert kwargs == {"cwd": Path(__file__).resolve().parents[2], "check": True, "shell": False}
        start = date.fromisoformat(command[command.index("--min-date") + 1])
        end = date.fromisoformat(command[command.index("--max-date") + 1])
        calls.append((start, end, "--no-dedup-with-db" in command))
        if fail is not None:
            fail(command, len(calls))
        for value in iter_dates(start, end):
            db[value] = set(expected.get(value, set()))
        if interrupt_after is not None and len(calls) == interrupt_after:
            raise KeyboardInterrupt("worker stopped after child pipeline")

    return run


def orchestrator(store, expected, db, calls, **kwargs):
    return CoverageReconciliationOrchestrator(
        store,
        listings_fetcher=kwargs.pop("listings_fetcher", listing_fetcher(expected)),
        db_fetcher=lambda _url, value: set(db.get(date.fromisoformat(value), set())),
        source_quarantine_fetcher=kwargs.pop(
            "source_quarantine_fetcher", lambda *_args, **_kwargs: set()
        ),
        run_command=kwargs.pop("run_command", pipeline_runner(expected, db, calls)),
        sleep=lambda _seconds: None,
        today=lambda: TODAY,
        **kwargs,
    )


def test_multi_month_range_splits_into_bounded_audit_chunks():
    chunks = list(date_chunks(date(2026, 3, 1), date(2026, 6, 15), 31))

    assert len(chunks) == 4
    assert all((end - start).days + 1 <= 31 for start, end in chunks)


def test_more_than_seven_missing_dates_use_bounded_child_chunks_and_succeed():
    start, end = date(2026, 8, 1), date(2026, 8, 10)
    expected = {value: {value.isoformat()} for value in iter_dates(start, end)}
    db = {value: set() for value in iter_dates(start, end)}
    calls = []
    store = MemoryReconciliationStore(start, end)

    result = orchestrator(store, expected, db, calls).run(1)

    assert result["status"] == "succeeded"
    assert [(call[0], call[1]) for call in calls] == [
        (start, start + timedelta(days=6)),
        (start + timedelta(days=7), end),
    ]
    assert all((end - start).days + 1 <= 7 for start, end, _refresh in calls)


def test_interrupted_reconciliation_reaudits_and_skips_completed_child_pipeline():
    start, end = date(2026, 8, 1), date(2026, 8, 10)
    expected = {value: {value.isoformat()} for value in iter_dates(start, end)}
    db = {value: set() for value in iter_dates(start, end)}
    calls = []
    store = MemoryReconciliationStore(start, end)
    first = orchestrator(
        store,
        expected,
        db,
        calls,
        run_command=pipeline_runner(expected, db, calls, interrupt_after=1),
    )

    with pytest.raises(KeyboardInterrupt):
        first.run(1)
    result = orchestrator(store, expected, db, calls).run(1)

    assert result["status"] == "succeeded"
    assert calls.count((start, start + timedelta(days=6), False)) == 1
    assert calls[-1] == (start + timedelta(days=7), end, False)


def test_auto_future_horizon_uses_canonical_dates_and_bounded_windows():
    observed = TODAY + timedelta(days=40)
    calls = []
    store = MemoryReconciliationStore(TODAY, None, requested_max="auto")
    store.run["future_horizon_days"] = 90
    expected = {observed: {"future"}}
    worker = orchestrator(store, expected, {}, [], listings_fetcher=listing_fetcher(expected, calls))

    assert worker.discover_max_date(store.get_run(1)) == observed
    assert all((date.fromisoformat(end) - date.fromisoformat(start)).days + 1 <= 31 for start, end in calls)


def test_auto_future_horizon_reports_exhaustion_near_boundary():
    store = MemoryReconciliationStore(TODAY, None, requested_max="auto")
    store.run["future_horizon_days"] = 40
    boundary_event = TODAY + timedelta(days=39)
    worker = orchestrator(store, {boundary_event: {"edge"}}, {}, [])

    with pytest.raises(FutureHorizonExhausted):
        worker.discover_max_date(store.get_run(1))


def test_retryable_ra_error_retries_but_non_retryable_does_not():
    store = MemoryReconciliationStore(TODAY, TODAY)
    attempts = 0

    def transient(_start, _end):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RAListingError("temporary", retryable=True, reason="http_429")
        return []

    worker = orchestrator(store, {}, {}, [], listings_fetcher=transient)
    assert worker._fetch_listings(TODAY, TODAY, 3) == []
    assert attempts == 2

    attempts = 0

    def invalid(_start, _end):
        nonlocal attempts
        attempts += 1
        raise RAListingError("invalid schema", retryable=False)

    with pytest.raises(RAListingError):
        orchestrator(store, {}, {}, [], listings_fetcher=invalid)._fetch_listings(TODAY, TODAY, 3)
    assert attempts == 1


def test_ra_empty_db_empty_is_safe_but_ra_empty_db_present_is_conflict():
    store = MemoryReconciliationStore(TODAY, TODAY)
    safe = orchestrator(store, {}, {}, [])._audit_window(store.get_run(1), TODAY, TODAY)[0]
    assert safe["status"] == "empty_on_ra"

    conflict = orchestrator(store, {}, {TODAY: {"existing"}}, [])._audit_window(
        store.get_run(1), TODAY, TODAY
    )[0]
    assert conflict["status"] == "ra_empty_conflict"


def test_active_source_quarantine_is_visible_but_not_repairable_missing():
    target = TODAY - timedelta(days=1)
    store = MemoryReconciliationStore(target, target)
    observed = []
    worker = orchestrator(
        store,
        {target: {"123"}},
        {target: set()},
        [],
        source_quarantine_fetcher=lambda database_url, event_ids, ttl_days: (
            observed.append((database_url, event_ids, ttl_days)) or {"123"}
        ),
    )

    audit = worker._audit_window(store.get_run(1), target, target)[0]

    assert audit["raw_missing_count"] == 1
    assert audit["raw_missing_event_ids"] == ["123"]
    assert audit["source_unresolvable_count"] == 1
    assert audit["source_unresolvable_event_ids"] == ["123"]
    assert audit["missing_count"] == 0
    assert audit["missing_event_ids"] == []
    assert audit["db_count"] == 0
    assert audit["status"] == "complete_with_source_unresolvable"
    assert observed == [(store.database_url, {"123"}, 7)]


def test_persisted_source_quarantine_ttl_is_used_after_environment_changes(monkeypatch):
    target = TODAY - timedelta(days=1)
    store = MemoryReconciliationStore(target, target)
    store.run["source_quarantine_ttl_days"] = 11
    observed = []
    monkeypatch.setenv("RA_EVENT_DETAIL_QUARANTINE_TTL_DAYS", "1")
    worker = orchestrator(
        store,
        {target: {"123"}},
        {target: set()},
        [],
        source_quarantine_fetcher=lambda _url, _ids, ttl: observed.append(ttl) or set(),
    )

    worker._audit_window(store.get_run(1), target, target)

    assert observed == [11]


def test_expired_source_quarantine_does_not_suppress_missing_event():
    target = TODAY - timedelta(days=1)
    store = MemoryReconciliationStore(target, target)
    audit = orchestrator(
        store,
        {target: {"123"}},
        {target: set()},
        [],
        source_quarantine_fetcher=lambda *_args: set(),
    )._audit_window(store.get_run(1), target, target)[0]

    assert audit["raw_missing_count"] == 1
    assert audit["source_unresolvable_count"] == 0
    assert audit["missing_count"] == 1
    assert audit["missing_event_ids"] == ["123"]
    assert audit["status"] == "missing_events"


def test_final_reconciliation_can_succeed_with_visible_source_unresolvable():
    target = TODAY - timedelta(days=1)
    store = MemoryReconciliationStore(target, target)
    result = orchestrator(
        store,
        {target: {"123"}},
        {target: set()},
        [],
        source_quarantine_fetcher=lambda *_args: {"123"},
    ).run(1)

    assert result["status"] == "succeeded"
    assert result["final_missing"] == 0
    assert result["dates"][0]["final_audit_status"] == (
        "complete_with_source_unresolvable"
    )
    assert result["dates"][0]["final_audit"]["db_count"] == 0
    assert result["dates"][0]["final_audit"]["source_unresolvable_event_ids"] == ["123"]


def test_historical_complete_date_skips_pipeline_and_future_complete_date_refreshes():
    historical = TODAY - timedelta(days=1)
    expected = {historical: {"old"}, TODAY: {"future"}}
    db = {historical: {"old"}, TODAY: {"future"}}
    calls = []
    store = MemoryReconciliationStore(historical, TODAY)

    result = orchestrator(store, expected, db, calls).run(1)

    assert result["status"] == "succeeded"
    assert calls == [(TODAY, TODAY, True)]
    assert result["dates"][0]["pipeline_status"] == "skipped"


def test_transient_pipeline_lock_contention_retries_same_chunk():
    target = TODAY - timedelta(days=1)
    expected = {target: {"missing"}}
    db = {target: set()}
    calls = []

    def fail(command, attempt):
        if attempt == 1:
            raise subprocess.CalledProcessError(75, command)

    store = MemoryReconciliationStore(target, target)
    result = orchestrator(
        store, expected, db, calls,
        run_command=pipeline_runner(expected, db, calls, fail=fail),
    ).run(1)

    assert result["status"] == "succeeded"
    assert len(calls) == 2
    assert result["dates"][0]["pipeline_attempt_count"] == 2


def test_non_retryable_pipeline_failure_marks_run_failed_and_preserves_state():
    target = TODAY - timedelta(days=1)
    expected = {target: {"missing"}}
    db = {target: set()}
    calls = []

    def fail(command, _attempt):
        raise subprocess.CalledProcessError(2, command)

    store = MemoryReconciliationStore(target, target)
    with pytest.raises(subprocess.CalledProcessError):
        orchestrator(
            store, expected, db, calls,
            run_command=pipeline_runner(expected, db, calls, fail=fail),
        ).run(1)

    assert store.run["status"] == "failed"
    assert store.run["dates"][0]["pipeline_status"] == "failed"


def test_final_full_range_audit_is_mandatory_and_missing_blocks_success():
    target = TODAY - timedelta(days=1)
    store = MemoryReconciliationStore(target, target)
    calls = 0

    def db_fetcher(_url, _value):
        nonlocal calls
        calls += 1
        return {"event"} if calls == 1 else set()

    worker = CoverageReconciliationOrchestrator(
        store,
        listings_fetcher=lambda *_args: [{"id": "event", "date": f"{target}T20:00:00Z"}],
        db_fetcher=db_fetcher,
        source_quarantine_fetcher=lambda *_args, **_kwargs: set(),
        run_command=lambda *_args, **_kwargs: pytest.fail("healthy initial range should not backfill"),
        today=lambda: TODAY,
    )
    result = worker.run(1)

    assert calls == 2
    assert result["status"] == "failed"
    assert result["final_missing"] == 1


def test_resumed_historical_run_repairs_gap_first_discovered_by_final_audit():
    target = TODAY - timedelta(days=1)
    expected = {target: {"existing"}}
    db = {target: {"existing"}}
    calls = []
    fetches = 0

    def changing_listings(start, end):
        nonlocal fetches
        fetches += 1
        if fetches == 2:
            expected[target].add("late")
        return listing_fetcher(expected)(start, end)

    store = MemoryReconciliationStore(target, target)
    first = orchestrator(store, expected, db, calls, listings_fetcher=changing_listings).run(1)

    assert first["status"] == "failed"
    assert first["initial_missing"] == 0
    assert first["final_missing"] == 1
    assert calls == []

    resumed = orchestrator(store, expected, db, calls).run(1)

    assert resumed["status"] == "succeeded"
    assert resumed["final_missing"] == 0
    assert calls == [(target, target, False)]


def test_resumed_future_run_refreshes_gap_first_discovered_by_final_audit():
    expected = {TODAY: {"existing"}}
    db = {TODAY: {"existing"}}
    calls = []
    fetches = 0

    def changing_listings(start, end):
        nonlocal fetches
        fetches += 1
        if fetches == 3:
            expected[TODAY].add("late")
        return listing_fetcher(expected)(start, end)

    store = MemoryReconciliationStore(TODAY, TODAY)
    first = orchestrator(store, expected, db, calls, listings_fetcher=changing_listings).run(1)

    assert first["status"] == "failed"
    assert first["dates"][0]["pipeline_status"] == "succeeded"
    assert calls == [(TODAY, TODAY, True)]

    resumed = orchestrator(store, expected, db, calls).run(1)

    assert resumed["status"] == "succeeded"
    assert resumed["final_missing"] == 0
    assert calls == [(TODAY, TODAY, True), (TODAY, TODAY, True)]


def test_resume_does_not_reprocess_healthy_completed_dates():
    healthy = TODAY - timedelta(days=2)
    changed = TODAY - timedelta(days=1)
    expected = {healthy: {"healthy"}, changed: {"existing", "late"}}
    db = {healthy: {"healthy"}, changed: {"existing"}}
    calls = []
    store = MemoryReconciliationStore(healthy, changed)
    store.run["initial_missing"] = 0
    for row in store.run["dates"]:
        row["initial_audit_status"] = "complete"
        row["initial_missing_count"] = 0
        row["pipeline_status"] = "skipped"

    result = orchestrator(store, expected, db, calls).run(1)

    assert result["status"] == "succeeded"
    assert calls == [(changed, changed, False)]


def test_each_convergence_invocation_is_bounded_when_gap_keeps_reappearing():
    target = TODAY - timedelta(days=1)
    expected = {target: {"event-0"}}
    db = {target: set()}
    calls = []
    final_audits = 0

    def never_converges(start, end):
        nonlocal final_audits
        result = listing_fetcher(expected)(start, end)
        if db[target] == expected[target]:
            final_audits += 1
            expected[target].add(f"event-{final_audits}")
            result = listing_fetcher(expected)(start, end)
        return result

    store = MemoryReconciliationStore(target, target)
    result = orchestrator(store, expected, db, calls, listings_fetcher=never_converges).run(1)

    assert result["status"] == "failed"
    assert result["final_missing"] == 1
    assert len(calls) == 1
    assert store.run["dates"][0]["pipeline_attempt_count"] == 1


def test_berlin_calendar_today_controls_midnight_boundary():
    assert berlin_calendar_today(datetime(2026, 8, 29, 22, 30, tzinfo=timezone.utc)) == date(2026, 8, 30)
    assert berlin_calendar_today(datetime(2026, 8, 29, 21, 30, tzinfo=timezone.utc)) == date(2026, 8, 29)


def test_worker_lifetime_is_independent_of_launcher_and_command_is_fixed():
    store = MemoryReconciliationStore(TODAY, TODAY)
    processed = []

    class FakeOrchestrator:
        def __init__(self, received):
            assert received is store

        def run(self, run_id):
            processed.append(run_id)
            store.update_run(run_id, status="succeeded", final_missing=0, completed=True)
            return store.get_run(run_id)

    assert process_next_reconciliation(
        store, worker_id="worker-test", orchestrator_factory=FakeOrchestrator
    ) is True
    assert processed == [1]
    compose = (Path(__file__).resolve().parents[2] / "docker-compose.prod.yml").read_text()
    assert 'command: ["python", "-m", "app.coverage_reconcile_worker"]' in compose


def test_status_is_compact_read_only_and_launcher_only_enqueues(monkeypatch, capsys):
    store = MemoryReconciliationStore(TODAY, TODAY)
    before = copy.deepcopy(store.run)
    compact = public_reconciliation_status(store.get_latest())
    assert "dates" not in compact
    assert store.run == before

    class FakeStore:
        def __init__(self, _url):
            pass

        def get_latest(self):
            return store.get_latest()

    monkeypatch.setenv("DATABASE_URL", "postgresql://test/scenegraph")
    monkeypatch.setattr(coverage_reconcile, "CoverageReconciliationStore", FakeStore)
    monkeypatch.setattr("sys.argv", ["coverage_reconcile.py", "status", "--latest"])
    assert coverage_reconcile.main() == 0
    assert json.loads(capsys.readouterr().out)["id"] == 1

    enqueued = []

    class FakeLaunchStore:
        def __init__(self, _url):
            pass

        def enqueue(self, **values):
            enqueued.append(values)
            return {"id": 12, "status": "queued"}

    monkeypatch.setattr(coverage_reconcile, "CoverageReconciliationStore", FakeLaunchStore)
    monkeypatch.setenv("RA_EVENT_DETAIL_QUARANTINE_TTL_DAYS", "13")
    monkeypatch.setattr(
        "sys.argv",
        [
            "coverage_reconcile.py",
            "--min-date", "2026-03-01",
            "--max-date", "auto",
            "--background",
        ],
    )
    assert coverage_reconcile.main() == 0
    assert json.loads(capsys.readouterr().out)["run_id"] == 12
    assert enqueued[0]["requested_max_date"] == "auto"
    assert enqueued[0]["source_quarantine_ttl_days"] == 13


def test_existing_coverage_limits_remain_unchanged():
    from app.coverage import CoverageConfig

    config = CoverageConfig()
    assert config.max_audit_days == 31
    assert config.max_backfills_per_run == 7
    assert all((end - start).days + 1 <= 7 for start, end in contiguous_date_chunks(
        [TODAY + timedelta(days=value) for value in range(15)], 7
    ))
