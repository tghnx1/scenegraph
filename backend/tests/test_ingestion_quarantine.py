from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

if "httpx" not in sys.modules:
    sys.modules["httpx"] = __import__("types").ModuleType("httpx")
if "openai" not in sys.modules:
    openai_stub = __import__("types").ModuleType("openai")
    openai_stub.OpenAI = object
    openai_stub.AzureOpenAI = object
    sys.modules["openai"] = openai_stub
if "psycopg" not in sys.modules:
    psycopg_stub = __import__("types").ModuleType("psycopg")
    psycopg_stub.Connection = object
    psycopg_stub.connect = lambda *args, **kwargs: None
    rows_stub = __import__("types").ModuleType("psycopg.rows")
    rows_stub.dict_row = object()
    psycopg_stub.rows = rows_stub
    sys.modules["psycopg"] = psycopg_stub
    sys.modules["psycopg.rows"] = rows_stub
from app.ingestion_quarantine import (
    classify_extraction_error,
    extraction_error_metadata,
    fetch_active_source_quarantine_ids,
    quarantine_entity,
    resolve_quarantine,
    safe_extraction_error_message,
)


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.attempt_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=()):
        self.calls.append((query, params))
        if "INSERT INTO ingestion_quarantine" in query:
            self.attempt_count += 1

    def fetchone(self):
        return {"attempt_count": self.attempt_count}


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1


def test_classify_extraction_error_is_narrow():
    assert classify_extraction_error(RuntimeError("content_filter")) == "content_filter"
    assert classify_extraction_error(json.JSONDecodeError("bad", "{", 1)) == "malformed_json"
    assert classify_extraction_error(RuntimeError("rate limit")) is None


def test_quarantine_upsert_and_resolve_are_db_backed():
    connection = FakeConnection()
    error = json.JSONDecodeError("bad", '{"tags":"', 9)

    first_attempt = quarantine_entity(
        connection,
        entity_type="artist",
        entity_id=1883,
        stage="extract_artist_tags",
        error=error,
        metadata={"provider": "azure", "reason": "malformed_json"},
    )
    second_attempt = quarantine_entity(
        connection,
        entity_type="artist",
        entity_id=1883,
        stage="extract_artist_tags",
        error=error,
        metadata={"provider": "azure", "reason": "malformed_json"},
    )
    resolve_quarantine(
        connection,
        entity_type="artist",
        entity_id=1883,
        stage="extract_artist_tags",
    )

    assert first_attempt == 1
    assert second_attempt == 2
    assert connection.commits == 3
    insert_params = connection.cursor_obj.calls[0][1]
    assert insert_params[:4] == ("artist", 1883, "extract_artist_tags", "malformed_json")
    assert json.loads(insert_params[5]) == {"provider": "azure", "reason": "malformed_json"}
    assert "ON CONFLICT (entity_type, entity_id, stage) WHERE resolved_at IS NULL" in connection.cursor_obj.calls[0][0]
    assert "resolved_at = CURRENT_TIMESTAMP" in connection.cursor_obj.calls[2][0]


def test_content_filter_metadata_keeps_only_safe_category_and_severity():
    error = RuntimeError("content_filter")
    error.body = {
        "error": {
            "innererror": {
                "content_filter_result": {
                    "sexual": {"filtered": True, "severity": "medium"},
                    "violence": {"filtered": False, "severity": "safe"},
                }
            },
            "prompt": "must not be copied",
        }
    }

    assert extraction_error_metadata(error) == {
        "provider": "azure",
        "reason": "content_filter",
        "filter_category": "sexual",
        "filter_severity": "medium",
    }
    assert safe_extraction_error_message(error) == (
        "Provider rejected entity content under content_filter policy"
    )


def test_source_quarantine_lookup_applies_ttl_and_stage(monkeypatch):
    captured = {}

    class LookupCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, query, params):
            captured["query"] = query
            captured["params"] = params

        def fetchall(self):
            return [{"entity_id": 123}]

    class LookupConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def cursor(self):
            return LookupCursor()

    monkeypatch.setattr(
        sys.modules["psycopg"],
        "connect",
        lambda *_args, **_kwargs: LookupConnection(),
    )
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)

    result = fetch_active_source_quarantine_ids(
        "postgresql://test/scenegraph", {"123", "456"}, 7, now=now
    )

    assert result == {"123"}
    assert "stage = 'ra_event_detail'" in captured["query"]
    assert captured["params"][0].isoformat() == "2026-08-25T00:00:00+00:00"
    assert captured["params"][1] == [123, 456]
