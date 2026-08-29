from __future__ import annotations

import os
import types

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://scenegraph:change-me@db:5432/scenegraph")

from scripts import extract_event_tags


class FakeConnection:
    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def base_args(**overrides):
    values = {
        "event_id": None,
        "after_id": None,
        "limit": None,
        "offset": 0,
        "batch_size": 1,
        "force": False,
        "dry_run": False,
        "no_chunk_fallback": False,
        "continue_on_error": False,
        "event_ids_file": None,
    }
    values.update(overrides)
    return types.SimpleNamespace(**values)


def configure_run(monkeypatch, *, events, extract_one, fallback):
    connection = FakeConnection()
    written: list[int] = []
    quarantined: list[int] = []
    resolved: list[int] = []
    monkeypatch.setattr(extract_event_tags, "parse_args", lambda: base_args())
    monkeypatch.setattr(
        extract_event_tags.EventTagExtractionConfig,
        "from_env",
        classmethod(lambda cls: types.SimpleNamespace(extractor_key="extractor", model="test")),
    )
    monkeypatch.setattr(extract_event_tags, "ensure_provider_env", lambda config: None)
    monkeypatch.setattr(extract_event_tags, "create_extraction_client", lambda: object())
    monkeypatch.setattr(extract_event_tags, "fetch_event_texts", lambda connection, **kwargs: events)
    monkeypatch.setattr(extract_event_tags, "has_current_event_tag_extraction", lambda connection, **kwargs: False)
    monkeypatch.setattr(extract_event_tags, "extract_event_tags_with_llm", extract_one)
    monkeypatch.setattr(extract_event_tags, "extract_event_tags_with_chunked_fallback", fallback)
    monkeypatch.setattr(
        extract_event_tags,
        "quarantine_entity",
        lambda connection, **kwargs: quarantined.append(kwargs["entity_id"]) or 2,
    )
    monkeypatch.setattr(
        extract_event_tags,
        "resolve_quarantine",
        lambda connection, **kwargs: resolved.append(kwargs["entity_id"]),
    )
    monkeypatch.setattr(
        extract_event_tags,
        "replace_event_tags",
        lambda connection, **kwargs: written.append(kwargs["event_id"]),
    )
    monkeypatch.setattr(extract_event_tags.psycopg, "connect", lambda *args, **kwargs: connection)
    return written, quarantined, resolved


def test_event_content_filter_is_quarantined_and_next_event_runs(monkeypatch, capsys):
    events = [
        {"id": 1, "name": "Blocked", "title": "Blocked", "description_text": "blocked", "text": "blocked"},
        {"id": 2, "name": "Healthy", "title": "Healthy", "description_text": "healthy", "text": "healthy"},
    ]

    def extract_one(*args, **kwargs):
        if kwargs["event_name"] == "Blocked":
            raise RuntimeError("content_filter")
        return []

    written, quarantined, resolved = configure_run(
        monkeypatch,
        events=events,
        extract_one=extract_one,
        fallback=lambda *args, **kwargs: types.SimpleNamespace(
            tags=[], total_chunks=2, processed_chunks=0, skipped_chunks=2
        ),
    )

    extract_event_tags.main()

    stderr = capsys.readouterr().err
    assert quarantined == [1]
    assert written == [2]
    assert resolved == [2]
    assert "error_type=content_filter; attempts=2" in stderr
    assert "quarantined=1; failed=0; remaining=0/2" in stderr


def test_unrelated_event_exception_fails_script(monkeypatch):
    event = {"id": 1, "name": "Broken", "title": "Broken", "description_text": "bad", "text": "bad"}
    written, quarantined, _ = configure_run(
        monkeypatch,
        events=[event],
        extract_one=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("socket exploded")),
        fallback=lambda *args, **kwargs: None,
    )

    with pytest.raises(RuntimeError, match="socket exploded"):
        extract_event_tags.main()

    assert quarantined == []
    assert written == []
