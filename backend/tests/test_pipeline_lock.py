from __future__ import annotations

import pytest

from app.pipeline_lock import (
    PIPELINE_ADVISORY_LOCK_KEY,
    PipelineAlreadyRunningError,
    acquire_pipeline_lock,
    release_pipeline_lock,
)


class FakeCursor:
    def __init__(self, acquired):
        self.acquired = acquired
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, query, params):
        self.executions.append((query, params))

    def fetchone(self):
        return (self.acquired,)


class FakeConnection:
    def __init__(self, acquired):
        self.cursor_instance = FakeCursor(acquired)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def test_pipeline_advisory_lock_is_held_until_explicit_release(monkeypatch):
    connection = FakeConnection(True)
    monkeypatch.setattr("app.pipeline_lock.psycopg.connect", lambda *_args, **_kwargs: connection)

    acquired = acquire_pipeline_lock("postgresql://test/scenegraph")

    assert acquired is connection
    assert connection.closed is False
    release_pipeline_lock(connection)
    assert connection.closed is True
    assert connection.cursor_instance.executions[-1][1] == (PIPELINE_ADVISORY_LOCK_KEY,)


def test_full_pipeline_cli_marks_lock_contention_as_transient(monkeypatch, capsys):
    from scripts import full_pipeline

    monkeypatch.setattr(
        full_pipeline,
        "main",
        lambda: (_ for _ in ()).throw(
            full_pipeline.PipelineAlreadyRunningError("pipeline busy")
        ),
    )

    assert full_pipeline.cli_main() == 75
    assert "Temporary lock contention" in capsys.readouterr().err


def test_concurrent_pipeline_is_rejected_and_connection_closed(monkeypatch):
    connection = FakeConnection(False)
    monkeypatch.setattr("app.pipeline_lock.psycopg.connect", lambda *_args, **_kwargs: connection)

    with pytest.raises(PipelineAlreadyRunningError, match="Another ingestion"):
        acquire_pipeline_lock("postgresql://test/scenegraph")

    assert connection.closed is True
