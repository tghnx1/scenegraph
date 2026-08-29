from __future__ import annotations

import subprocess
import types

import pytest

from app import quarantine


def retry_args(**overrides):
    values = {
        "command": "retry",
        "entity_type": None,
        "stage": None,
        "entity_id": None,
        "limit": 100,
        "dry_run": False,
    }
    values.update(overrides)
    return types.SimpleNamespace(**values)


def artist_item():
    return {"entity_type": "artist", "entity_id": 1883, "stage": "extract_artist_tags"}


def test_filters_are_forwarded_to_quarantine_query(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setenv("DATABASE_URL", "postgresql://db/scenegraph")
    monkeypatch.setattr(
        quarantine,
        "fetch_unresolved_quarantine",
        lambda database_url, **kwargs: captured.append({"database_url": database_url, **kwargs}) or [],
    )

    items = quarantine._load_items(
        retry_args(entity_type="event", stage="extract_event_tags", entity_id=42, limit=5)
    )

    assert items == []
    assert captured == [
        {
            "database_url": "postgresql://db/scenegraph",
            "entity_type": "event",
            "stage": "extract_event_tags",
            "entity_id": 42,
            "limit": 5,
        }
    ]


def test_retry_success_uses_existing_extractor_and_resolves(monkeypatch):
    state = {"resolved": False}
    commands: list[list[str]] = []
    monkeypatch.setattr(quarantine, "_load_items", lambda args: [artist_item()])

    def run(command, *, cwd, check):
        commands.append(command)
        state["resolved"] = True
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(quarantine.subprocess, "run", run)

    assert quarantine.retry_items(retry_args()) == 0
    assert state["resolved"] is True
    assert commands[0][-3:] == ["--artist-id", "1883", "--force"]


def test_retry_recoverable_failure_remains_unresolved(monkeypatch):
    state = {"resolved": False, "attempts": 1}
    monkeypatch.setattr(quarantine, "_load_items", lambda args: [artist_item()])

    def run(command, *, cwd, check):
        state["attempts"] += 1
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(quarantine.subprocess, "run", run)

    assert quarantine.retry_items(retry_args()) == 0
    assert state == {"resolved": False, "attempts": 2}


def test_retry_systemic_failure_stops(monkeypatch):
    monkeypatch.setattr(quarantine, "_load_items", lambda args: [artist_item()])

    def run(command, *, cwd, check):
        raise subprocess.CalledProcessError(3, command)

    monkeypatch.setattr(quarantine.subprocess, "run", run)

    with pytest.raises(subprocess.CalledProcessError):
        quarantine.retry_items(retry_args())


def test_retry_dry_run_delegates_without_mutating_state(monkeypatch):
    state = {"resolved": False, "attempts": 1}
    commands: list[list[str]] = []
    monkeypatch.setattr(quarantine, "_load_items", lambda args: [artist_item()])
    monkeypatch.setattr(
        quarantine.subprocess,
        "run",
        lambda command, *, cwd, check: commands.append(command) or subprocess.CompletedProcess(command, 0),
    )

    assert quarantine.retry_items(retry_args(dry_run=True)) == 0
    assert state == {"resolved": False, "attempts": 1}
    assert commands[0][-1] == "--dry-run"
