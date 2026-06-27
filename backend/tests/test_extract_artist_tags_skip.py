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
    psycopg_stub.connect = lambda *args, **kwargs: None
    rows_stub = types.ModuleType("psycopg.rows")
    rows_stub.dict_row = object()
    psycopg_stub.rows = rows_stub
    sys.modules["psycopg"] = psycopg_stub
    sys.modules["psycopg.rows"] = rows_stub

from scripts import extract_artist_tags


class FakeCursor:
    def __init__(self):
        self.executed: list[tuple[str, tuple | list]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query: str, params=()):
        self.executed.append((query, params))

    def fetchall(self):
        return []

    def fetchone(self):
        return None


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_artist_tag_extraction_skips_existing_current_run(monkeypatch):
    args = types.SimpleNamespace(
        artist_id=None,
        after_id=None,
        limit=None,
        batch_size=1,
        force=False,
        dry_run=False,
        no_chunk_fallback=True,
        continue_on_error=False,
        artist_ids_file=None,
    )
    fake_connection = FakeConnection()
    artists = [
        {"id": 1, "name": "Kept Artist", "biography": "bio", "_text_hash": "hash-1"},
        {"id": 2, "name": "Needs Extract", "biography": "bio 2", "_text_hash": "hash-2"},
    ]
    processed_ids: list[int] = []
    llm_calls: list[int] = []

    monkeypatch.setattr(extract_artist_tags, "parse_args", lambda: args)
    monkeypatch.setattr(
        extract_artist_tags.TagExtractionConfig,
        "from_env",
        classmethod(
            lambda cls: types.SimpleNamespace(
                azure_endpoint="https://example.openai.azure.com",
                api_version="2025-01-01-preview",
                extractor_key="extractor",
                model="gpt-test",
            )
        ),
    )
    monkeypatch.setattr(extract_artist_tags, "ensure_provider_env", lambda config: None)
    monkeypatch.setattr(extract_artist_tags, "create_extraction_client", lambda config: object())
    monkeypatch.setattr(
        extract_artist_tags,
        "fetch_artist_biographies",
        lambda connection, **kwargs: artists,
    )
    monkeypatch.setattr(
        extract_artist_tags,
        "has_current_artist_tag_extraction",
        lambda connection, **kwargs: kwargs["artist_id"] == 1,
    )
    monkeypatch.setattr(
        extract_artist_tags,
        "extract_artist_tags_with_llm",
        lambda *args, **kwargs: (
            llm_calls.append(kwargs["artist_name"]),
            [types.SimpleNamespace(tag_type="style", tag_value="techno", confidence=1.0, evidence="evidence")],
        )[1],
    )
    monkeypatch.setattr(
        extract_artist_tags,
        "replace_artist_tags",
        lambda connection, **kwargs: processed_ids.append(kwargs["artist_id"]),
    )
    monkeypatch.setattr(extract_artist_tags.psycopg, "connect", lambda *args, **kwargs: fake_connection, raising=False)

    monkeypatch.setattr(extract_artist_tags, "print_batch_progress", lambda **kwargs: None)

    extract_artist_tags.main()

    assert processed_ids == [2]
    assert llm_calls == ["Needs Extract"]
