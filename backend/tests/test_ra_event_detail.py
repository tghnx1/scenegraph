from __future__ import annotations

import json
import urllib.error
from types import SimpleNamespace

import pytest

from parsers.graphql_parser import parse_past_events as parser


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class RawResponse(FakeResponse):
    def read(self):
        return self.payload


def valid_payload(event_id="123"):
    return {
        "data": {
            "event": {
                "id": event_id,
                "title": "Event",
                "date": "2026-08-30T20:00:00Z",
            }
        }
    }


def test_http_502_then_success_retries_and_returns_event():
    responses = iter(
        (
            urllib.error.HTTPError(parser.URL, 502, "bad gateway", {}, None),
            FakeResponse(valid_payload()),
        )
    )
    sleeps = []

    def opener(*_args, **_kwargs):
        response = next(responses)
        if isinstance(response, BaseException):
            raise response
        return response

    result = parser.fetch_single_event("123", opener=opener, sleep=sleeps.append)

    assert result.event["id"] == "123"
    assert result.attempts == 2
    assert sleeps == [1.0]


def test_malformed_json_then_success_retries_and_returns_event():
    responses = iter((RawResponse(b'{"data":{"event":'), FakeResponse(valid_payload())))
    sleeps = []

    result = parser.fetch_single_event(
        "123", opener=lambda *_args, **_kwargs: next(responses), sleep=sleeps.append
    )

    assert result.event["id"] == "123"
    assert result.attempts == 2
    assert sleeps == [1.0]


def test_http_504_exhaustion_is_retryable_and_cli_returns_75(monkeypatch):
    attempts = 0

    def opener(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise urllib.error.HTTPError(parser.URL, 504, "gateway timeout", {}, None)

    with pytest.raises(parser.EventDetailTransientError) as captured:
        parser.fetch_single_event("123", opener=opener, sleep=lambda _seconds: None)

    assert attempts == 3
    assert captured.value.reason == "http_504"
    assert captured.value.http_status == 504

    monkeypatch.setattr(parser, "main", lambda: (_ for _ in ()).throw(captured.value))
    assert parser.cli_main() == 75


def test_event_null_is_confirmed_with_bounded_attempts():
    attempts = 0

    def opener(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        return FakeResponse({"data": {"event": None}})

    with pytest.raises(parser.EventDetailUnresolvableError) as captured:
        parser.fetch_single_event("123", opener=opener, sleep=lambda _seconds: None)

    assert attempts == 3
    assert captured.value.reason == "event_null"
    assert captured.value.retryable is False


def parser_args(tmp_path, *, database_url="postgresql://test/scenegraph"):
    return SimpleNamespace(
        out=tmp_path / "events.json",
        checkpoint_every=50,
        min_date="2026-08-30",
        max_date="2026-08-30",
        dedup_db=False,
        database_url=database_url,
        existing_event_ids_file=None,
        refresh_existing_in_range=True,
    )


def configure_single_listing(monkeypatch, tmp_path):
    args = parser_args(tmp_path)
    monkeypatch.setattr(parser, "parse_args", lambda: args)
    monkeypatch.setattr(parser, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(parser, "fetch_source_quarantined_event_ids", lambda _url: set())
    monkeypatch.setattr(
        parser,
        "fetch_event_listing_page_ids_with_curl",
        lambda *_args, **kwargs: ["123"] if kwargs.get("page", _args[2]) == 1 else [],
    )
    monkeypatch.setattr(parser.time, "sleep", lambda _seconds: None)
    return args


def test_source_unresolvable_is_quarantined_without_fake_event(monkeypatch, tmp_path):
    args = configure_single_listing(monkeypatch, tmp_path)
    quarantined = []
    monkeypatch.setattr(
        parser,
        "fetch_single_event",
        lambda _event_id: (_ for _ in ()).throw(
            parser.EventDetailUnresolvableError("123", "event_null", retryable=False)
        ),
    )
    monkeypatch.setattr(
        parser,
        "quarantine_source_unresolvable",
        lambda database_url, error, **metadata: quarantined.append(
            (database_url, error.event_id, error.reason, metadata)
        ),
    )

    assert parser.main() == 0
    assert json.loads(args.out.read_text(encoding="utf-8")) == []
    assert quarantined == [
        (
            "postgresql://test/scenegraph",
            "123",
            "event_null",
            {"min_date": "2026-08-30", "max_date": "2026-08-30"},
        )
    ]


def test_quarantine_persistence_failure_is_not_swallowed(monkeypatch, tmp_path):
    configure_single_listing(monkeypatch, tmp_path)
    monkeypatch.setattr(
        parser,
        "fetch_single_event",
        lambda _event_id: (_ for _ in ()).throw(
            parser.EventDetailUnresolvableError("123", "event_null", retryable=False)
        ),
    )
    monkeypatch.setattr(
        parser,
        "quarantine_source_unresolvable",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )

    with pytest.raises(parser.EventDetailSystemError) as captured:
        parser.main()

    assert captured.value.reason == "quarantine_persistence_failed"


def test_successful_later_fetch_resolves_source_quarantine(monkeypatch, tmp_path):
    args = configure_single_listing(monkeypatch, tmp_path)
    monkeypatch.setattr(parser, "fetch_source_quarantined_event_ids", lambda _url: {"123"})
    monkeypatch.setattr(
        parser,
        "fetch_single_event",
        lambda _event_id: parser.EventDetailResult(valid_payload()["data"]["event"], 1),
    )
    resolved = []
    monkeypatch.setattr(
        parser,
        "resolve_source_quarantine",
        lambda database_url, event_id: resolved.append((database_url, event_id)),
    )

    assert parser.main() == 0
    assert [item["id"] for item in json.loads(args.out.read_text(encoding="utf-8"))] == ["123"]
    assert resolved == [("postgresql://test/scenegraph", "123")]


def test_unresolvable_without_database_is_explicit_failure(monkeypatch):
    error = parser.EventDetailUnresolvableError("123", "event_null", retryable=False)
    monkeypatch.setattr(parser, "main", lambda: (_ for _ in ()).throw(error))

    assert parser.cli_main() == 1
