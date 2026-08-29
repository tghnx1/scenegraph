from __future__ import annotations

import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app import daily_ingestion


BERLIN = ZoneInfo("Europe/Berlin")


def test_resolves_previous_berlin_calendar_day():
    target = daily_ingestion.resolve_target_date(
        now=datetime(2026, 8, 26, 4, 0, tzinfo=BERLIN),
        environ={},
    )

    assert target.isoformat() == "2026-08-25"


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 3, 29, 4, 0, tzinfo=BERLIN), "2026-03-28"),
        (datetime(2026, 10, 25, 4, 0, tzinfo=BERLIN), "2026-10-24"),
    ],
)
def test_resolves_previous_calendar_day_across_dst_boundaries(now, expected):
    assert daily_ingestion.resolve_target_date(now=now, environ={}).isoformat() == expected


def test_explicit_target_date_override_is_used_exactly():
    target = daily_ingestion.resolve_target_date(
        now=datetime(2026, 8, 26, 4, 0, tzinfo=BERLIN),
        environ={"DAILY_INGEST_DATE": "2026-08-25"},
    )

    assert target.isoformat() == "2026-08-25"


@pytest.mark.parametrize("value", ["2026-02-30", "25-08-2026", "2026-8-25"])
def test_invalid_target_date_override_fails_clearly(value):
    with pytest.raises(ValueError, match="DAILY_INGEST_DATE"):
        daily_ingestion.resolve_target_date(environ={"DAILY_INGEST_DATE": value})


def test_pipeline_uses_identical_min_and_max_dates_and_then_scheduler(tmp_path):
    calls: list[tuple[list[str], object, bool]] = []

    def fake_run(command, *, cwd, check):
        calls.append((command, cwd, check))
        return subprocess.CompletedProcess(command, 0)

    result = daily_ingestion.run_daily_ingestion(
        environ={
            "DAILY_INGEST_DATE": "2026-08-25",
            "DAILY_INGEST_ARTIFACTS_DIR": str(tmp_path),
        },
        run_command=fake_run,
    )

    assert result == 0
    pipeline_command = calls[0][0]
    assert pipeline_command[pipeline_command.index("--min-date") + 1] == "2026-08-25"
    assert pipeline_command[pipeline_command.index("--max-date") + 1] == "2026-08-25"
    assert "--skip-bio" in pipeline_command
    assert "--skip-tags" not in pipeline_command
    assert "--skip-embeddings" not in pipeline_command
    assert calls[1][0][-2:] == ["-m", "app.recommendations.scheduler"]
    assert all(check is True for _, _, check in calls)


def test_scheduler_does_not_run_when_ingestion_fails():
    calls: list[list[str]] = []

    def fake_run(command, *, cwd, check):
        calls.append(command)
        raise subprocess.CalledProcessError(7, command)

    with pytest.raises(subprocess.CalledProcessError):
        daily_ingestion.run_daily_ingestion(
            environ={"DAILY_INGEST_DATE": "2026-08-25"},
            run_command=fake_run,
        )

    assert len(calls) == 1


def test_scheduler_runs_after_pipeline_succeeds_with_quarantined_entities(tmp_path):
    calls: list[list[str]] = []
    pipeline_had_quarantine = {"value": False}

    def fake_run(command, *, cwd, check):
        calls.append(command)
        if "full_pipeline.py" in " ".join(command):
            pipeline_had_quarantine["value"] = True
        return subprocess.CompletedProcess(command, 0)

    assert daily_ingestion.run_daily_ingestion(
        environ={
            "DAILY_INGEST_DATE": "2026-08-25",
            "DAILY_INGEST_ARTIFACTS_DIR": str(tmp_path),
        },
        run_command=fake_run,
    ) == 0

    assert pipeline_had_quarantine["value"] is True
    assert calls[1][-2:] == ["-m", "app.recommendations.scheduler"]
