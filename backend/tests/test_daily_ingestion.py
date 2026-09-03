from __future__ import annotations

import subprocess
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app import daily_ingestion
from app.event_dates import shift_calendar_months


BERLIN = ZoneInfo("Europe/Berlin")
REFERENCE_DATE = date(2026, 9, 3)


class FakeStore:
    database_url = "postgresql://test/scenegraph"

    def __init__(self, *, lock_available: bool = True):
        self.lock = object() if lock_available else None
        self.enqueue_values = None
        self.updates = []
        self.released = []

    def acquire_worker_lock(self):
        return self.lock

    def release_worker_lock(self, lock):
        self.released.append(lock)

    def enqueue(self, **values):
        self.enqueue_values = values
        return {"id": 17, "status": "queued"}

    def update_run(self, run_id, **values):
        self.updates.append((run_id, values))


def coverage_result(
    *,
    source_unresolvable: int = 0,
    initial_missing: int = 1,
    final_missing: int = 0,
):
    return {
        "id": 17,
        "status": "succeeded",
        "initial_missing": initial_missing,
        "final_missing": final_missing,
        "dates": [
            {
                "final_audit": {
                    "ra_count": 3,
                    "db_count": 3,
                    "extra_event_ids": ["extra"],
                    "source_unresolvable_count": source_unresolvable,
                }
            }
        ],
    }


def orchestrator_factory(result, steps, *, error=None):
    class FakeOrchestrator:
        def __init__(self, store, *, today):
            assert isinstance(store, FakeStore)
            assert today() == REFERENCE_DATE

        def run(self, run_id):
            assert run_id == 17
            steps.append("coverage")
            if error is not None:
                raise error
            return result

    return FakeOrchestrator


def daily_environment(tmp_path):
    return {
        "DATABASE_URL": "postgresql://test/scenegraph",
        "DAILY_INGEST_DATE": REFERENCE_DATE.isoformat(),
        "DAILY_INGEST_ARTIFACTS_DIR": str(tmp_path),
    }


def test_resolves_current_berlin_calendar_day():
    target = daily_ingestion.resolve_target_date(
        now=datetime(2026, 9, 3, 4, 0, tzinfo=BERLIN),
        environ={},
    )

    assert target == REFERENCE_DATE


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 3, 29, 4, 0, tzinfo=BERLIN),
        datetime(2026, 10, 25, 4, 0, tzinfo=BERLIN),
    ],
)
def test_resolves_current_calendar_day_across_dst_boundaries(now):
    assert daily_ingestion.resolve_target_date(now=now, environ={}) == now.date()


def test_explicit_target_date_override_is_reference_today():
    target = daily_ingestion.resolve_target_date(
        now=datetime(2026, 8, 26, 4, 0, tzinfo=BERLIN),
        environ={"DAILY_INGEST_DATE": "2026-09-03"},
    )

    assert target == REFERENCE_DATE


@pytest.mark.parametrize("value", ["2026-02-30", "03-09-2026", "2026-9-3"])
def test_invalid_target_date_override_fails_clearly(value):
    with pytest.raises(ValueError, match="DAILY_INGEST_DATE"):
        daily_ingestion.resolve_target_date(environ={"DAILY_INGEST_DATE": value})


def test_daily_ranges_use_calendar_month_arithmetic():
    assert daily_ingestion.daily_date_ranges(REFERENCE_DATE) == {
        "coverage_min": date(2026, 6, 3),
        "coverage_max": date(2026, 12, 3),
        "refresh_min": REFERENCE_DATE,
        "refresh_max": date(2026, 10, 3),
    }


@pytest.mark.parametrize(
    ("value", "months", "expected"),
    [
        (date(2026, 3, 31), -1, date(2026, 2, 28)),
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2024, 1, 31), 1, date(2024, 2, 29)),
        (date(2024, 3, 31), -1, date(2024, 2, 29)),
    ],
)
def test_shift_calendar_months_clamps_month_end(value, months, expected):
    assert shift_calendar_months(value, months) == expected


def test_coverage_then_forced_refresh_then_scheduler_once(tmp_path, capsys):
    store = FakeStore()
    steps = []
    commands = []

    def fake_run(command, *, cwd, check):
        commands.append((command, cwd, check))
        steps.append("scheduler" if "app.recommendations.scheduler" in command else "refresh")
        return subprocess.CompletedProcess(command, 0)

    result = daily_ingestion.run_daily_ingestion(
        environ=daily_environment(tmp_path),
        run_command=fake_run,
        store_factory=lambda _url: store,
        orchestrator_factory=orchestrator_factory(coverage_result(), steps),
    )

    assert result == 0
    assert steps == ["coverage", "refresh", "scheduler"]
    assert store.enqueue_values["min_date"] == date(2026, 6, 3)
    assert store.enqueue_values["requested_max_date"] == "2026-12-03"
    assert store.enqueue_values["refresh_all_future"] is False
    refresh_command = commands[0][0]
    assert refresh_command[refresh_command.index("--min-date") + 1] == "2026-09-03"
    assert refresh_command[refresh_command.index("--max-date") + 1] == "2026-10-03"
    assert "--skip-bio" in refresh_command
    assert "--no-dedup-with-db" in refresh_command
    assert "--force" not in refresh_command
    assert commands[1][0][-2:] == ["-m", "app.recommendations.scheduler"]
    assert store.released == [store.lock]
    output = capsys.readouterr().out
    assert "missing=1; final_missing=0" in output
    assert "extra=1; repaired=1" in output
    assert "Forced event refresh: succeeded" in output


def test_existing_nearby_event_skips_gap_repair_but_is_forced_refreshed(tmp_path):
    nearby_event_date = REFERENCE_DATE + timedelta(days=20)
    store = FakeStore()
    steps = []
    commands = []

    def fake_run(command, *, cwd, check):
        commands.append(command)
        steps.append("scheduler" if "app.recommendations.scheduler" in command else "refresh")
        return subprocess.CompletedProcess(command, 0)

    assert daily_ingestion.run_daily_ingestion(
        environ=daily_environment(tmp_path),
        run_command=fake_run,
        store_factory=lambda _url: store,
        orchestrator_factory=orchestrator_factory(
            coverage_result(initial_missing=0, final_missing=0), steps
        ),
    ) == 0

    refresh_command = commands[0]
    refresh_min = date.fromisoformat(refresh_command[refresh_command.index("--min-date") + 1])
    refresh_max = date.fromisoformat(refresh_command[refresh_command.index("--max-date") + 1])
    assert refresh_min <= nearby_event_date <= refresh_max
    assert "--no-dedup-with-db" in refresh_command
    assert steps == ["coverage", "refresh", "scheduler"]


def test_scheduler_does_not_run_when_coverage_fails(tmp_path):
    store = FakeStore()
    steps = []
    commands = []

    with pytest.raises(RuntimeError, match="coverage failed"):
        daily_ingestion.run_daily_ingestion(
            environ=daily_environment(tmp_path),
            run_command=lambda command, **_kwargs: commands.append(command),
            store_factory=lambda _url: store,
            orchestrator_factory=orchestrator_factory(
                coverage_result(), steps, error=RuntimeError("coverage failed")
            ),
        )

    assert steps == ["coverage"]
    assert commands == []
    assert store.released == [store.lock]


def test_unsuccessful_coverage_status_blocks_refresh_and_scheduler(tmp_path):
    store = FakeStore()
    steps = []
    commands = []
    failed_result = coverage_result()
    failed_result["status"] = "failed"
    failed_result["final_missing"] = 1

    with pytest.raises(daily_ingestion.DailyCoverageError, match="status=failed"):
        daily_ingestion.run_daily_ingestion(
            environ=daily_environment(tmp_path),
            run_command=lambda command, **_kwargs: commands.append(command),
            store_factory=lambda _url: store,
            orchestrator_factory=orchestrator_factory(failed_result, steps),
        )

    assert steps == ["coverage"]
    assert commands == []
    assert store.released == [store.lock]


def test_scheduler_does_not_run_when_forced_refresh_fails(tmp_path):
    store = FakeStore()
    steps = []
    commands = []

    def failing_refresh(command, *, cwd, check):
        commands.append(command)
        raise subprocess.CalledProcessError(7, command)

    with pytest.raises(subprocess.CalledProcessError):
        daily_ingestion.run_daily_ingestion(
            environ=daily_environment(tmp_path),
            run_command=failing_refresh,
            store_factory=lambda _url: store,
            orchestrator_factory=orchestrator_factory(coverage_result(), steps),
        )

    assert steps == ["coverage"]
    assert len(commands) == 1
    assert "full_pipeline.py" in " ".join(commands[0])
    assert store.released == [store.lock]


def test_source_quarantine_does_not_block_refresh_or_scheduler(tmp_path, capsys):
    store = FakeStore()
    steps = []

    def fake_run(command, *, cwd, check):
        steps.append("scheduler" if "app.recommendations.scheduler" in command else "refresh")
        return subprocess.CompletedProcess(command, 0)

    assert daily_ingestion.run_daily_ingestion(
        environ=daily_environment(tmp_path),
        run_command=fake_run,
        store_factory=lambda _url: store,
        orchestrator_factory=orchestrator_factory(
            coverage_result(source_unresolvable=1), steps
        ),
    ) == 0

    assert steps == ["coverage", "refresh", "scheduler"]
    assert "source_unresolvable=1" in capsys.readouterr().out


def test_busy_reconciliation_lock_is_retryable(tmp_path):
    store = FakeStore(lock_available=False)

    with pytest.raises(daily_ingestion.DailyIngestionBusyError):
        daily_ingestion.run_daily_ingestion(
            environ=daily_environment(tmp_path),
            store_factory=lambda _url: store,
        )
