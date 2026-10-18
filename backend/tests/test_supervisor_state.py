from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.supervisor.state import DeterministicSupervisor, JsonStateStore, ProductRunReader


class FakeCursor:
    def __init__(self, database: "FakeDatabase") -> None:
        self.database = database
        self.rows: list[dict] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: tuple = ()) -> None:
        normalized = " ".join(query.split())
        self.database.queries.append((normalized, params))
        if "FROM import_runs" in normalized:
            self.rows = [self.database.run]
        elif "FROM import_run_stages" in normalized:
            self.rows = self.database.stages
        elif "FROM ingestion_quarantine" in normalized:
            self.rows = self.database.quarantine
        else:
            raise AssertionError(f"unexpected query: {normalized}")

    def fetchone(self) -> dict | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[dict]:
        return list(self.rows)


class FakeDatabase:
    def __init__(self, error: str | None = None) -> None:
        self.queries: list[tuple[str, tuple]] = []
        self.run = {
            "id": 192, "pipeline_name": "full-pipeline", "status": "failed" if error else "succeeded",
            "min_date": "2026-12-31", "max_date": "2027-01-04", "event_count": 25, "artist_count": 89,
            "events_imported": 25, "artists_imported": 80, "event_tags": 25, "artist_tags": 70,
            "event_embeddings": 25, "artist_embeddings": 80, "error": error,
            "started_at": "2026-10-18T14:06:50Z", "finished_at": "2026-10-18T14:08:20Z", "updated_at": "2026-10-18T14:08:20Z",
        }
        self.stages = [{"stage_name": "extract-artist-tags", "status": "failed" if error else "succeeded", "duration_ms": 250, "error": error, "started_at": "2026-10-18T14:07:00Z", "finished_at": "2026-10-18T14:08:00Z", "updated_at": "2026-10-18T14:08:00Z"}]
        self.quarantine = [{"entity_type": "artist", "unresolved_count": 1, "attempts": 2}]

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)


class FakeTelegram:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send(self, message: str) -> None:
        self.messages.append(message)


def test_supervisor_projects_progress_and_uses_select_only() -> None:
    database = FakeDatabase()
    snapshot = ProductRunReader(database).read()
    assert snapshot is not None
    assert snapshot.remaining_events == 0
    assert snapshot.remaining_artists == 9
    assert all(query.startswith("SELECT") for query, _ in database.queries)


def test_quota_state_and_notification_survive_restart_without_raw_secret() -> None:
    database = FakeDatabase("provider quota usage limit; api_key=sk-secret")
    telegram = FakeTelegram()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "state.json"
        first = DeterministicSupervisor(ProductRunReader(database), JsonStateStore(path), telegram)
        first_report = first.observe(192)
        restarted = DeterministicSupervisor(ProductRunReader(database), JsonStateStore(path), telegram)
        second_report = restarted.observe(192)

        assert first_report["failure_category"] == "quota_exhausted"
        assert second_report["progress"]["artists"]["remaining"] == 9
        assert len(telegram.messages) == 1
        assert "sk-secret" not in json.dumps(JsonStateStore(path).load())


def test_success_notification_is_deduplicated() -> None:
    database = FakeDatabase()
    telegram = FakeTelegram()
    with tempfile.TemporaryDirectory() as directory:
        supervisor = DeterministicSupervisor(
            ProductRunReader(database),
            JsonStateStore(Path(directory) / "state.json"),
            telegram,
        )
        supervisor.observe(192)
        supervisor.observe(192)

    assert telegram.messages == ["Ingestion succeeded: run=192; events=25; artists=80"]
