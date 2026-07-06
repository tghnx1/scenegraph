from __future__ import annotations

import importlib.util
import json
import sys

import pytest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_extract_artists_module():
    module_name = "scenegraph_extract_artists_for_test"
    module_path = REPO_ROOT / "parsers" / "extract_artists.py"
    if not module_path.exists():
        pytest.skip("parsers/ is not mounted in this test environment")
    spec = importlib.util.spec_from_file_location(
        module_name,
        module_path,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_artist_bio_complete_policy_skips_only_complete_or_terminal_artists():
    module = load_extract_artists_module()

    assert module.artist_bio_is_complete({"biography": "Existing bio", "biography_status": None}) is True
    assert module.artist_bio_is_complete({"biography": "", "biography_status": "ok"}) is True
    assert module.artist_bio_is_complete({"biography": "", "biography_status": "not_found"}) is True
    assert module.artist_bio_is_complete({"biography": "", "biography_status": "empty"}) is True
    assert module.artist_bio_is_complete({"biography": "", "biography_status": "manually_edited"}) is True

    assert module.artist_bio_is_complete(None) is False
    assert module.artist_bio_is_complete({"biography": "", "biography_status": None}) is False
    assert module.artist_bio_is_complete({"biography": "", "biography_status": "blocked"}) is False
    assert module.artist_bio_is_complete({"biography": "", "biography_status": "timeout"}) is False
    assert module.artist_bio_is_complete({"biography": "", "biography_status": "error"}) is False


def test_extract_artists_includes_existing_artists_that_need_bio_refresh(monkeypatch, tmp_path):
    module = load_extract_artists_module()
    events_path = tmp_path / "events.json"
    output_path = tmp_path / "artists.json"
    events_path.write_text(
        json.dumps(
            [
                {
                    "id": 1,
                    "artists": [
                        {"id": "10", "contentUrl": "/dj/complete"},
                        {"id": "11", "contentUrl": "/dj/missing-bio"},
                        {"id": "12", "contentUrl": "/dj/blocked"},
                        {"id": "13", "contentUrl": "/dj/new"},
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        module,
        "load_existing_artist_bio_state_from_db",
        lambda database_url: {
            "10": {"ra_artist_id": "10", "biography": "Already parsed.", "biography_status": "ok"},
            "11": {"ra_artist_id": "11", "biography": None, "biography_status": None},
            "12": {"ra_artist_id": "12", "biography": "", "biography_status": "blocked"},
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extract_artists.py",
            "--input",
            str(events_path),
            "--output",
            str(output_path),
            "--dedup-db",
            "--database-url",
            "postgresql://example",
        ],
    )

    module.main()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert [artist["id"] for artist in payload] == ["11", "12", "13"]
    assert payload[0]["url"] == "https://ra.co/dj/missing-bio/biography"
