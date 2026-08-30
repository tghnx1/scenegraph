from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app import coverage
from app.coverage import CoverageConfig, CoverageOperations, fetch_db_event_ids
from app.quarantine import build_retry_command


DATE = "2026-08-15"


def make_operations(**overrides) -> CoverageOperations:
    values = {
        "min_date": DATE,
        "max_date": DATE,
        "database_url": "postgresql://test/scenegraph",
        "ra_fetcher": lambda _start, _end: {"1", "2"},
        "db_fetcher": lambda _url, _date: {"1", "2"},
        "quarantine_fetcher": lambda *_args, **_kwargs: [],
        "quarantine_retry": lambda *_args: None,
        "run_command": lambda *_args, **_kwargs: None,
    }
    values.update(overrides)
    return CoverageOperations(**values)


def test_audit_date_uses_canonical_ra_ids_and_calculates_gap():
    operations = make_operations(
        ra_fetcher=lambda _start, _end: {1, 2, 3},
        db_fetcher=lambda _url, _date: {1, 2},
    )

    result = operations.audit_date(DATE)

    assert result["missing_event_ids"] == ["3"]
    assert result["extra_event_ids"] == []
    assert result["missing_count"] == 1
    assert result["status"] == "missing_events"


def test_audit_date_complete_and_titles_are_not_inputs():
    operations = make_operations()

    result = operations.audit_date(DATE)

    assert result["status"] == "complete"
    assert result["missing_count"] == 0
    assert "title" not in result


def test_db_audit_uses_berlin_calendar_date_and_canonical_ids(monkeypatch):
    captured = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, query, params):
            captured["query"] = query
            captured["params"] = params

        def fetchall(self):
            return [{"ra_event_id": 12}, {"ra_event_id": "13"}]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(coverage.psycopg, "connect", lambda *_args, **_kwargs: FakeConnection())

    result = fetch_db_event_ids("postgresql://test/scenegraph", DATE)

    assert result == {"12", "13"}
    assert "event_date AT TIME ZONE %s" in captured["query"]
    assert captured["params"] == ("Europe/Berlin", DATE)


def test_audit_failure_is_structured_and_cannot_trigger_backfill():
    operations = make_operations(
        apply=True,
        ra_fetcher=lambda _start, _end: (_ for _ in ()).throw(ConnectionError("offline")),
    )

    result = operations.audit_date(DATE)

    assert result["status"] == "audit_failed"
    assert result["error_type"] == "ConnectionError"
    with pytest.raises(RuntimeError, match="missing events"):
        operations.run_backfill(DATE)


def test_range_audit_is_compact_and_enforces_configured_limit():
    operations = make_operations(
        min_date="2026-08-14",
        config=CoverageConfig(max_audit_days=2),
    )

    result = operations.audit_range("2026-08-14", DATE)

    assert result["status"] == "complete"
    assert len(result["dates"]) == 2
    assert "db_event_ids" not in result["dates"][0]
    with pytest.raises(ValueError, match="maximum is 2"):
        make_operations(min_date="2026-08-13", config=CoverageConfig(max_audit_days=2))


def test_read_only_and_complete_audits_never_start_backfill():
    calls: list[list[str]] = []
    read_only = make_operations(
        ra_fetcher=lambda _start, _end: {"1", "2"},
        db_fetcher=lambda _url, _date: {"1"},
        run_command=lambda command, **_kwargs: calls.append(command),
    )
    read_only.audit_date(DATE)

    with pytest.raises(PermissionError, match="--apply"):
        read_only.run_backfill(DATE)

    complete = make_operations(apply=True, run_command=lambda command, **_kwargs: calls.append(command))
    complete.audit_date(DATE)
    with pytest.raises(RuntimeError, match="missing events"):
        complete.run_backfill(DATE)
    assert calls == []


def test_apply_runs_fixed_argv_with_no_shell_and_verification_controls_repair(tmp_path):
    db_results = iter(({"1"}, {"1"}, {"1", "2"}))
    calls: list[tuple[list[str], dict]] = []
    operations = make_operations(
        apply=True,
        config=CoverageConfig(artifacts_dir=tmp_path),
        db_fetcher=lambda _url, _date: next(db_results),
        run_command=lambda command, **kwargs: calls.append((command, kwargs)),
    )

    operations.audit_date(DATE)
    assert operations.run_backfill(DATE)["status"] == "succeeded"
    assert operations.verify_date(DATE)["status"] == "still_missing"
    assert operations.verify_date(DATE)["status"] == "repaired"

    command, kwargs = calls[0]
    assert command[2:6] == ["--min-date", DATE, "--max-date", DATE]
    assert command[-3:] == ["--artifacts-dir", str(tmp_path), "--skip-bio"]
    assert kwargs["shell"] is False
    assert kwargs["check"] is True


def test_backfill_rejects_outside_date_duplicate_and_limit():
    operations = make_operations(
        min_date="2026-08-14",
        apply=True,
        config=CoverageConfig(max_backfills_per_run=1),
        ra_fetcher=lambda _start, _end: {"1"},
        db_fetcher=lambda _url, _date: set(),
    )
    operations.audit_date("2026-08-14")
    operations.audit_date(DATE)
    operations.run_backfill("2026-08-14")

    with pytest.raises(RuntimeError, match="already been backfilled"):
        operations.run_backfill("2026-08-14")
    with pytest.raises(RuntimeError, match="limit reached"):
        operations.run_backfill(DATE)
    with pytest.raises(ValueError, match="Invalid YYYY-MM-DD"):
        operations.run_backfill("2026-08-16; rm -rf /tmp/example")


def test_systemic_pipeline_error_is_logged_and_propagated():
    error = subprocess.CalledProcessError(9, ["full_pipeline.py"])
    operations = make_operations(
        apply=True,
        ra_fetcher=lambda _start, _end: {"1"},
        db_fetcher=lambda _url, _date: set(),
        run_command=lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )
    operations.audit_date(DATE)

    with pytest.raises(subprocess.CalledProcessError):
        operations.run_backfill(DATE)
    assert operations.actions[-1]["status"] == "failed"
    assert operations.actions[-1]["error_type"] == "CalledProcessError"


def test_quarantine_is_reported_separately_and_never_creates_coverage_gap():
    item = {
        "entity_type": "event",
        "entity_id": 19907,
        "stage": "extract_event_tags",
        "error_type": "content_filter",
        "attempt_count": 2,
    }
    operations = make_operations(quarantine_fetcher=lambda *_args, **_kwargs: [item])

    assert operations.audit_date(DATE)["status"] == "complete"
    status = operations.quarantine_status()

    assert status["events"] == 1
    assert status["items"] == [item]
    assert operations.backfilled_dates == set()


def test_quarantine_retry_is_allowlisted_bounded_and_attempt_limited():
    retried: list[tuple[str, int, str]] = []
    item = {
        "entity_type": "artist",
        "entity_id": 1883,
        "stage": "extract_artist_tags",
        "error_type": "malformed_json",
        "attempt_count": 2,
    }
    resolved_fetches = iter(([item], []))
    operations = make_operations(
        apply=True,
        allow_quarantine_retry=True,
        quarantine_fetcher=lambda *_args, **_kwargs: next(resolved_fetches),
        quarantine_retry=lambda *args: retried.append(args),
    )

    assert operations.retry_quarantine("artist", 1883, "extract_artist_tags") == {
        "entity_type": "artist",
        "entity_id": 1883,
        "stage": "extract_artist_tags",
        "status": "resolved",
    }
    assert retried == [("artist", 1883, "extract_artist_tags")]
    with pytest.raises(RuntimeError, match="already been retried"):
        operations.retry_quarantine("artist", 1883, "extract_artist_tags")

    at_limit = {**item, "attempt_count": 3}
    limited = make_operations(
        apply=True,
        allow_quarantine_retry=True,
        quarantine_fetcher=lambda *_args, **_kwargs: [at_limit],
    )
    with pytest.raises(RuntimeError, match="retry limit"):
        limited.retry_quarantine("artist", 1883, "extract_artist_tags")


def test_quarantine_retry_reports_still_quarantined_with_new_attempt_count():
    before = {
        "entity_type": "event",
        "entity_id": 19907,
        "stage": "extract_event_tags",
        "error_type": "content_filter",
        "attempt_count": 1,
    }
    after = {**before, "attempt_count": 2}
    fetches = iter(([before], [after]))
    operations = make_operations(
        apply=True,
        allow_quarantine_retry=True,
        quarantine_fetcher=lambda *_args, **_kwargs: next(fetches),
    )

    result = operations.retry_quarantine("event", 19907, "extract_event_tags")

    assert result["status"] == "still_quarantined"
    assert result["attempt_count"] == 2


def test_quarantine_retry_delegates_allowlist_validation():
    operations = make_operations(
        apply=True,
        allow_quarantine_retry=True,
        quarantine_fetcher=lambda *_args, **_kwargs: [
            {
                "entity_type": "event",
                "entity_id": 1,
                "stage": "delete_database",
                "error_type": "unknown",
                "attempt_count": 1,
            }
        ],
        quarantine_retry=lambda *_args: (_ for _ in ()).throw(RuntimeError("unsupported target")),
    )

    with pytest.raises(RuntimeError, match="unsupported target"):
        operations.retry_quarantine("event", 1, "delete_database")

    with pytest.raises(RuntimeError, match="Unsupported quarantine retry target"):
        build_retry_command("event", 1, "delete_database")


def test_tool_results_and_final_report_are_json_compatible():
    operations = make_operations()
    operations.audit_range(DATE, DATE)
    operations.quarantine_status()

    assert json.loads(json.dumps(operations.report()))["audited_dates"] == [DATE]
