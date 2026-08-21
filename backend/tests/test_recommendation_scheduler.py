from contextlib import contextmanager

import pytest

from app.recommendations import jobs
from app.recommendations import scheduler


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, sql, _params=None):
        self.sql = sql

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows=()):
        self.cursor_instance = FakeCursor(rows)
        self.commits = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1


def test_scheduler_eligibility_requires_active_account_biography_and_three_connections():
    connection = FakeConnection([
        {
            "user_id": 101,
            "artist_id": 201,
            "has_biography": True,
            "manual_connection_count": 3,
        },
        {
            "user_id": 102,
            "artist_id": 202,
            "has_biography": False,
            "manual_connection_count": 5,
        },
        {
            "user_id": 103,
            "artist_id": 203,
            "has_biography": True,
            "manual_connection_count": 2,
        },
    ])

    targets = scheduler._eligible_recommendation_targets(connection)

    assert targets == [{"user_id": 101, "artist_id": 201}]
    normalized_sql = " ".join(connection.cursor_instance.sql.split())
    assert "u.status IN ('pending', 'approved')" in normalized_sql
    assert "a.biography_normalized" in normalized_sql
    assert "a.biography" in normalized_sql
    assert "COUNT(DISTINCT amc.connected_artist_id)" in normalized_sql


def test_scheduler_enqueues_each_eligible_target_once_and_exits(monkeypatch: pytest.MonkeyPatch):
    connection = FakeConnection()
    calls = []

    @contextmanager
    def fake_get_connection():
        yield connection

    monkeypatch.setattr(scheduler, "get_connection", fake_get_connection)
    monkeypatch.setattr(
        scheduler,
        "_eligible_recommendation_targets",
        lambda _connection: [
            {"user_id": 101, "artist_id": 201},
            {"user_id": 102, "artist_id": 202},
        ],
    )
    monkeypatch.setattr(
        scheduler,
        "enqueue_default_artist_promoter_recommendation_job",
        lambda _connection, **target: calls.append(target) or {"id": str(target["artist_id"])},
    )

    assert scheduler.run_scheduler() == 2
    assert calls == [
        {"user_id": 101, "artist_id": 201},
        {"user_id": 102, "artist_id": 202},
    ]
    assert connection.commits == 1


def test_default_scheduler_enqueue_reuses_create_recommendation_job(monkeypatch: pytest.MonkeyPatch):
    calls = []
    expected = {"id": "job-1", "status": "queued"}

    monkeypatch.setattr(
        jobs,
        "create_recommendation_job",
        lambda connection, **kwargs: calls.append((connection, kwargs)) or expected,
    )
    connection = object()

    result = jobs.enqueue_default_artist_promoter_recommendation_job(
        connection,
        user_id=101,
        artist_id=201,
    )

    assert result is expected
    assert calls == [(
        connection,
        {
            "user_id": 101,
            "artist_id": 201,
            "params": {"limit": 200, "debug": False},
        },
    )]


def test_scheduler_main_runs_once_and_returns(monkeypatch: pytest.MonkeyPatch):
    calls = []
    monkeypatch.setattr(scheduler, "run_scheduler", lambda: calls.append("run") or 0)

    scheduler.main()

    assert calls == ["run"]
