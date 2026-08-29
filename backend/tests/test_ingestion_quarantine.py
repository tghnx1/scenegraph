from __future__ import annotations

import json
import sys
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
from app.ingestion_quarantine import classify_extraction_error, quarantine_entity, resolve_quarantine


class FakeCursor:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=()):
        self.calls.append((query, params))


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

    quarantine_entity(
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

    assert connection.commits == 2
    insert_params = connection.cursor_obj.calls[0][1]
    assert insert_params[:4] == ("artist", 1883, "extract_artist_tags", "malformed_json")
    assert json.loads(insert_params[5]) == {"provider": "azure", "reason": "malformed_json"}
    assert "resolved_at = CURRENT_TIMESTAMP" in connection.cursor_obj.calls[1][0]
