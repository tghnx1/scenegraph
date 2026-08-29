from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import pytest

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


def _base_artist_args(**overrides):
    data = {
        "artist_id": None,
        "after_id": None,
        "limit": None,
        "batch_size": 1,
        "force": False,
        "dry_run": False,
        "no_chunk_fallback": False,
        "continue_on_error": False,
        "artist_ids_file": None,
    }
    data.update(overrides)
    return types.SimpleNamespace(**data)


def _setup_single_artist_run(monkeypatch, *, llm_side_effect=None, chunk_result=None):
    args = _base_artist_args()
    fake_connection = FakeConnection()
    artists = [{"id": 1883, "name": "Marvel Gold", "biography": "bio", "_text_hash": "hash-1883"}]
    replaced: list[tuple[int, list]] = []
    llm_calls: list[str] = []
    chunk_calls: list[str] = []

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
        lambda connection, **kwargs: False,
    )

    def fake_llm(*args, **kwargs):
        llm_calls.append(kwargs["artist_name"])
        if llm_side_effect is not None:
            raise llm_side_effect
        return [types.SimpleNamespace(tag_type="style", tag_value="techno", confidence=1.0, evidence="evidence")]

    def fake_chunked(*args, **kwargs):
        chunk_calls.append(kwargs["artist_name"])
        if chunk_result is not None:
            return chunk_result
        return types.SimpleNamespace(
            tags=[
                types.SimpleNamespace(tag_type="style", tag_value="techno", confidence=0.9, evidence="chunk"),
                types.SimpleNamespace(tag_type="role", tag_value="dj", confidence=0.8, evidence=None),
                types.SimpleNamespace(tag_type="role", tag_value="producer", confidence=0.7, evidence=None),
            ],
            total_chunks=2,
            processed_chunks=2,
            skipped_chunks=0,
        )

    monkeypatch.setattr(extract_artist_tags, "extract_artist_tags_with_llm", fake_llm)
    monkeypatch.setattr(extract_artist_tags, "extract_artist_tags_with_chunked_fallback", fake_chunked)
    monkeypatch.setattr(
        extract_artist_tags,
        "replace_artist_tags",
        lambda connection, **kwargs: replaced.append((kwargs["artist_id"], kwargs["tags"])),
    )
    monkeypatch.setattr(extract_artist_tags.psycopg, "connect", lambda *args, **kwargs: fake_connection, raising=False)
    monkeypatch.setattr(extract_artist_tags, "print_batch_progress", lambda **kwargs: None)

    return args, replaced, llm_calls, chunk_calls


def test_artist_tag_extraction_chunk_fallbacks_on_json_decode_error(monkeypatch, capsys):
    args, replaced, llm_calls, chunk_calls = _setup_single_artist_run(
        monkeypatch,
        llm_side_effect=json.JSONDecodeError("Unterminated string starting at", doc='{"tags":"', pos=9),
    )

    extract_artist_tags.main()

    captured = capsys.readouterr().err
    assert "reason=malformed_json" in captured
    assert "processed_chunks=2/2" in captured
    assert llm_calls == ["Marvel Gold"]
    assert chunk_calls == ["Marvel Gold"]
    assert replaced and replaced[0][0] == 1883
    assert [tag.tag_value for tag in replaced[0][1]] == ["techno", "dj", "producer"]


def test_artist_tag_extraction_keeps_failure_when_chunk_fallback_disabled_on_json_error(monkeypatch):
    args = _base_artist_args(no_chunk_fallback=True)
    fake_connection = FakeConnection()
    artists = [{"id": 1883, "name": "Marvel Gold", "biography": "bio", "_text_hash": "hash-1883"}]

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
    monkeypatch.setattr(extract_artist_tags, "fetch_artist_biographies", lambda connection, **kwargs: artists)
    monkeypatch.setattr(extract_artist_tags, "has_current_artist_tag_extraction", lambda connection, **kwargs: False)
    monkeypatch.setattr(
        extract_artist_tags,
        "extract_artist_tags_with_llm",
        lambda *args, **kwargs: (_ for _ in ()).throw(json.JSONDecodeError("bad", doc='{"tags":"', pos=9)),
    )
    monkeypatch.setattr(extract_artist_tags, "print_batch_progress", lambda **kwargs: None)
    monkeypatch.setattr(extract_artist_tags.psycopg, "connect", lambda *args, **kwargs: fake_connection, raising=False)

    with pytest.raises(json.JSONDecodeError):
        extract_artist_tags.main()


def test_artist_tag_extraction_chunk_fallbacks_on_content_filter(monkeypatch):
    args, replaced, llm_calls, chunk_calls = _setup_single_artist_run(
        monkeypatch,
        llm_side_effect=RuntimeError("content_filter"),
    )

    extract_artist_tags.main()

    assert llm_calls == ["Marvel Gold"]
    assert chunk_calls == ["Marvel Gold"]
    assert replaced and [tag.tag_value for tag in replaced[0][1]] == ["techno", "dj", "producer"]


def test_artist_tag_extraction_does_not_fallback_for_unrelated_error(monkeypatch):
    args = _base_artist_args()
    fake_connection = FakeConnection()
    artists = [{"id": 1883, "name": "Marvel Gold", "biography": "bio", "_text_hash": "hash-1883"}]
    chunk_calls: list[str] = []

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
    monkeypatch.setattr(extract_artist_tags, "fetch_artist_biographies", lambda connection, **kwargs: artists)
    monkeypatch.setattr(extract_artist_tags, "has_current_artist_tag_extraction", lambda connection, **kwargs: False)
    monkeypatch.setattr(
        extract_artist_tags,
        "extract_artist_tags_with_llm",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("boom")),
    )
    monkeypatch.setattr(
        extract_artist_tags,
        "extract_artist_tags_with_chunked_fallback",
        lambda *args, **kwargs: chunk_calls.append("called"),
    )
    monkeypatch.setattr(extract_artist_tags, "print_batch_progress", lambda **kwargs: None)
    monkeypatch.setattr(extract_artist_tags.psycopg, "connect", lambda *args, **kwargs: fake_connection, raising=False)

    with pytest.raises(ValueError):
        extract_artist_tags.main()

    assert chunk_calls == []


def test_artist_tag_extraction_success_does_not_fallback(monkeypatch):
    args, replaced, llm_calls, chunk_calls = _setup_single_artist_run(monkeypatch)

    extract_artist_tags.main()

    assert llm_calls == ["Marvel Gold"]
    assert chunk_calls == []
    assert replaced and [tag.tag_value for tag in replaced[0][1]] == ["techno"]
