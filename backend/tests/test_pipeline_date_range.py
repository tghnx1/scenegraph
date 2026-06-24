from __future__ import annotations

import importlib.util
import types
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def install_import_stubs() -> None:
    if "psycopg" not in sys.modules:
        psycopg_stub = types.ModuleType("psycopg")

        class _Connection:  # pragma: no cover - type placeholder for imports
            pass

        def _connect(*_args, **_kwargs):
            raise RuntimeError("psycopg stub should not be used during this test")

        psycopg_stub.Connection = _Connection
        psycopg_stub.connect = _connect
        rows_stub = types.ModuleType("psycopg.rows")
        rows_stub.dict_row = object()
        psycopg_stub.rows = rows_stub
        sys.modules["psycopg"] = psycopg_stub
        sys.modules["psycopg.rows"] = rows_stub

    if "openai" not in sys.modules:
        openai_stub = types.ModuleType("openai")
        openai_stub.OpenAI = object
        openai_stub.AzureOpenAI = object
        sys.modules["openai"] = openai_stub

    if "httpx" not in sys.modules:
        httpx_stub = types.ModuleType("httpx")
        sys.modules["httpx"] = httpx_stub


def test_today_range_collapses_to_one_chunk():
    module = load_module(
        "scenegraph_parse_past_events",
        REPO_ROOT / "parsers" / "graphql_parser" / "parse_past_events.py",
    )
    today = datetime.now().strftime("%Y-%m-%d")

    assert module.get_month_chunks(today, today) == [(today, today)]


def test_full_pipeline_forwards_today_range(monkeypatch, tmp_path):
    install_import_stubs()
    module = load_module(
        "scenegraph_full_pipeline",
        REPO_ROOT / "backend" / "scripts" / "full_pipeline.py",
    )
    today = datetime.now().strftime("%Y-%m-%d")
    events_json = tmp_path / "ra_berlin_past_events_2026.json"
    events_json.write_text(
        """
        [
          {"id": 1, "date": "%sT00:00:00.000", "artists": [{"id": 10}, {"id": 11}]},
          {"id": 2, "date": "2026-01-01T00:00:00.000", "artists": [{"id": 12}]}
        ]
        """
        % today,
        encoding="utf-8",
    )
    seen_commands: list[list[str]] = []
    seen_stages: list[str] = []

    monkeypatch.setattr(module, "ensure_writable_parent", lambda path: None)
    monkeypatch.setattr(module, "ensure_db_ready", lambda: None)
    monkeypatch.setattr(module, "ensure_playwright_available", lambda: None)
    monkeypatch.setattr(module, "ensure_cdp_ready", lambda cdp_url: None)
    monkeypatch.setattr(module, "ensure_provider_env", lambda skip_tags, skip_embeddings: None)
    monkeypatch.setattr(
        module,
        "run_stage",
        lambda name, command, cwd=None, env=None: (seen_stages.append(name), seen_commands.append(command)),
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "full_pipeline.py",
            "--min-date",
            today,
            "--max-date",
            today,
            "--events-json",
            str(events_json),
            "--skip-bio",
            "--skip-tags",
            "--skip-embeddings",
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    assert seen_stages == [
        "scrape-and-parse",
        "import-to-db",
        "backfill-normalized-texts",
        "validate-import",
    ]
    joined_commands = [" ".join(map(str, command)) for command in seen_commands]
    assert any("--events-min-date" in command and today in command for command in joined_commands)
    assert any("--events-max-date" in command and today in command for command in joined_commands)
    import_cmd = next(command for command in seen_commands if "import_events.py" in " ".join(map(str, command)))
    assert any(str(part).endswith(".import.json") for part in import_cmd)
    backfill_cmd = next(command for command in seen_commands if "backfill_normalized_texts.py" in " ".join(map(str, command)))
    assert any(str(part).endswith(".event_ids.txt") for part in backfill_cmd)
    assert any(str(part).endswith(".artist_ids.txt") for part in backfill_cmd)
    event_ids_file = next(Path(part) for part in backfill_cmd if str(part).endswith(".event_ids.txt"))
    artist_ids_file = next(Path(part) for part in backfill_cmd if str(part).endswith(".artist_ids.txt"))
    assert event_ids_file.read_text(encoding="utf-8").splitlines() == ["1"]
    assert artist_ids_file.read_text(encoding="utf-8").splitlines() == ["10", "11"]
