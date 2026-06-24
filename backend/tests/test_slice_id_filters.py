from __future__ import annotations

import os
import sys
import types
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://scenegraph:change-me@db:5432/scenegraph")

sys.path.append(str(Path(__file__).resolve().parents[1]))

if "httpx" not in sys.modules:
    sys.modules["httpx"] = types.ModuleType("httpx")
if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")
    openai_stub.OpenAI = object
    openai_stub.AzureOpenAI = object
    sys.modules["openai"] = openai_stub
if "psycopg" not in sys.modules:
    psycopg_stub = types.ModuleType("psycopg")

    class _Connection:  # pragma: no cover - import placeholder
        pass

    psycopg_stub.Connection = _Connection
    rows_stub = types.ModuleType("psycopg.rows")
    rows_stub.dict_row = object()
    psycopg_stub.rows = rows_stub
    sys.modules["psycopg"] = psycopg_stub
    sys.modules["psycopg.rows"] = rows_stub

from app.artist_tag_extraction import fetch_artist_biographies
from app.embeddings import fetch_entity_ids
from app.event_tag_extraction import fetch_event_texts


class FakeCursor:
    def __init__(self, rows: list[dict] | None = None):
        self.rows = rows or []
        self.executed: list[tuple[str, tuple | list]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query: str, params=()):
        self.executed.append((query, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self, rows: list[dict] | None = None):
        self.cursor_obj = FakeCursor(rows)

    def cursor(self):
        return self.cursor_obj


def test_fetch_event_texts_filters_by_ra_event_id():
    connection = FakeConnection(
        [{"id": 7, "name": "Event", "title": "Event", "description_text": "desc", "lineup_residual_text": "", "lineup_raw": "", "artist_names": [], "structured_genres": [], "text": "desc"}]
    )

    rows = fetch_event_texts(connection, event_ids=[111, 222])

    assert rows == connection.cursor_obj.rows
    query, params = connection.cursor_obj.executed[-1]
    assert "e.ra_event_id = ANY(%s)" in query
    assert params == [["111", "222"]]


def test_fetch_artist_biographies_filters_by_ra_artist_id():
    connection = FakeConnection([{"id": 9, "name": "Artist", "biography": "bio"}])

    rows = fetch_artist_biographies(connection, artist_ids=[333])

    assert rows == connection.cursor_obj.rows
    query, params = connection.cursor_obj.executed[-1]
    assert "ra_artist_id = ANY(%s)" in query
    assert params == [["333"]]


def test_fetch_entity_ids_filters_by_ra_id_and_returns_internal_ids():
    connection = FakeConnection([{"id": 42}])

    rows = fetch_entity_ids(connection, "event", ids=[444])

    assert rows == [42]
    query, params = connection.cursor_obj.executed[-1]
    assert "ra_event_id = ANY(%s)" in query
    assert params == [["444"]]
