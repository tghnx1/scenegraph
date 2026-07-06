from __future__ import annotations

import importlib.util
import subprocess
import types
import sys

import pytest
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def resolve_module_path(path: Path) -> Path:
    if path.exists():
        return path
    marker = ("backend", "scripts")
    parts = path.parts
    for index in range(len(parts) - 1):
        if parts[index:index + 2] == marker:
            backend_relative = Path(*parts[index + 1:])
            candidate = Path.cwd() / backend_relative
            if candidate.exists():
                return candidate
    if "parsers" in path.parts:
        pytest.skip(f"parser source is not mounted in this test environment: {path}")
    return path


def load_module(module_name: str, path: Path):
    path = resolve_module_path(path)
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
    assert any(str(part).endswith("import.json") for part in import_cmd)
    backfill_cmd = next(command for command in seen_commands if "backfill_normalized_texts.py" in " ".join(map(str, command)))
    assert any(str(part).endswith("event_ids.txt") for part in backfill_cmd)
    assert any(str(part).endswith("artist_ids.txt") for part in backfill_cmd)
    event_ids_file = next(Path(part) for part in backfill_cmd if str(part).endswith("event_ids.txt"))
    artist_ids_file = next(Path(part) for part in backfill_cmd if str(part).endswith("artist_ids.txt"))
    assert event_ids_file.read_text(encoding="utf-8").splitlines() == ["1"]
    assert artist_ids_file.read_text(encoding="utf-8").splitlines() == ["10", "11"]


def test_full_pipeline_runs_generate_embeddings_before_backfill_vectors(monkeypatch, tmp_path):
    install_import_stubs()
    module = load_module(
        "scenegraph_full_pipeline_order",
        REPO_ROOT / "backend" / "scripts" / "full_pipeline.py",
    )
    today = datetime.now().strftime("%Y-%m-%d")
    events_json = tmp_path / "ra_berlin_past_events_2026.json"
    events_json.write_text(
        """
        [
          {"id": 1, "date": "%sT00:00:00.000", "artists": [{"id": 10}]}
        ]
        """
        % today,
        encoding="utf-8",
    )
    seen_stages: list[str] = []

    monkeypatch.setattr(module, "ensure_writable_parent", lambda path: None)
    monkeypatch.setattr(module, "ensure_db_ready", lambda: None)
    monkeypatch.setattr(module, "ensure_playwright_available", lambda: None)
    monkeypatch.setattr(module, "ensure_cdp_ready", lambda cdp_url: None)
    monkeypatch.setattr(module, "ensure_provider_env", lambda skip_tags, skip_embeddings: None)
    monkeypatch.setattr(
        module,
        "run_stage",
        lambda name, command, cwd=None, env=None: seen_stages.append(name),
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
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    assert seen_stages == [
        "scrape-and-parse",
        "import-to-db",
        "backfill-normalized-texts",
        "generate-embeddings",
        "backfill-embedding-vectors",
        "validate-import",
    ]


def test_full_pipeline_filters_from_post_parse_archive(monkeypatch, tmp_path):
    install_import_stubs()
    module = load_module(
        "scenegraph_full_pipeline_post_parse",
        REPO_ROOT / "backend" / "scripts" / "full_pipeline.py",
    )
    today = datetime.now().strftime("%Y-%m-%d")
    events_json = tmp_path / "ra_berlin_past_events_2026.json"
    events_json.write_text(
        """
        [
          {"id": 99, "date": "2026-01-01T00:00:00.000", "artists": [{"id": 999}]}
        ]
        """,
        encoding="utf-8",
    )
    seen_stages: list[str] = []

    def fake_run_stage(name, command, cwd=None, env=None):
        seen_stages.append(name)
        if name == "scrape-and-parse":
            events_json.write_text(
                """
                [
                  {"id": 1, "date": "%sT00:00:00.000", "artists": [{"id": 10}]},
                  {"id": 2, "date": "2026-01-01T00:00:00.000", "artists": [{"id": 11}]}
                ]
                """
                % today,
                encoding="utf-8",
            )

    monkeypatch.setattr(module, "ensure_writable_parent", lambda path: None)
    monkeypatch.setattr(module, "ensure_db_ready", lambda: None)
    monkeypatch.setattr(module, "ensure_playwright_available", lambda: None)
    monkeypatch.setattr(module, "ensure_cdp_ready", lambda cdp_url: None)
    monkeypatch.setattr(module, "ensure_provider_env", lambda skip_tags, skip_embeddings: None)
    monkeypatch.setattr(module, "run_stage", fake_run_stage)

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
    import_file = events_json.with_name("import.json")
    assert import_file.read_text(encoding="utf-8").strip().startswith("[")
    assert '"id": 1' in import_file.read_text(encoding="utf-8")
    assert '"id": 2' not in import_file.read_text(encoding="utf-8")


def test_full_pipeline_uses_per_run_artifact_dir_by_default(monkeypatch, tmp_path):
    install_import_stubs()
    module = load_module(
        "scenegraph_full_pipeline_artifacts",
        REPO_ROOT / "backend" / "scripts" / "full_pipeline.py",
    )
    today = datetime.now().strftime("%Y-%m-%d")
    artifacts_dir = tmp_path / "import_runs"
    seen_commands: list[list[str]] = []

    monkeypatch.setattr(module, "ensure_writable_parent", lambda path: path.parent.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(module, "ensure_db_ready", lambda: None)
    monkeypatch.setattr(module, "ensure_playwright_available", lambda: None)
    monkeypatch.setattr(module, "ensure_cdp_ready", lambda cdp_url: None)
    monkeypatch.setattr(module, "ensure_provider_env", lambda skip_tags, skip_embeddings: None)

    def fake_run_stage(name, command, cwd=None, env=None):
        seen_commands.append(command)
        if name == "scrape-and-parse":
            events_json = Path(command[command.index("--events-json") + 1])
            events_json.parent.mkdir(parents=True, exist_ok=True)
            events_json.write_text(
                """
                [
                  {"id": 1, "date": "%sT00:00:00.000", "artists": [{"id": 10}]}
                ]
                """
                % today,
                encoding="utf-8",
            )

    monkeypatch.setattr(module, "run_stage", fake_run_stage)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "full_pipeline.py",
            "--min-date",
            today,
            "--max-date",
            today,
            "--artifacts-dir",
            str(artifacts_dir),
            "--skip-bio",
            "--skip-tags",
            "--skip-embeddings",
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    parse_cmd = seen_commands[0]
    events_json = Path(parse_cmd[parse_cmd.index("--events-json") + 1])
    assert events_json.parent.parent == artifacts_dir
    assert events_json.name == "events.json"
    assert (events_json.parent / "artists.json").parent == events_json.parent
    assert (events_json.parent / "import.json").exists()
    assert (events_json.parent / "event_ids.txt").read_text(encoding="utf-8").splitlines() == ["1"]


def test_full_pipeline_succeeds_when_date_filter_leaves_no_new_events(monkeypatch, tmp_path):
    install_import_stubs()
    module = load_module(
        "scenegraph_full_pipeline_empty_slice",
        REPO_ROOT / "backend" / "scripts" / "full_pipeline.py",
    )
    events_json = tmp_path / "events.json"
    seen_stages: list[str] = []

    monkeypatch.setattr(module, "ensure_writable_parent", lambda path: None)
    monkeypatch.setattr(module, "ensure_db_ready", lambda: None)
    monkeypatch.setattr(module, "ensure_playwright_available", lambda: None)
    monkeypatch.setattr(module, "ensure_cdp_ready", lambda cdp_url: None)
    monkeypatch.setattr(module, "ensure_provider_env", lambda skip_tags, skip_embeddings: None)

    def fake_run_stage(name, command, cwd=None, env=None):
        seen_stages.append(name)
        if name == "scrape-and-parse":
            events_json.write_text(
                """
                [
                  {"id": 2472941, "date": "2026-06-21T00:00:00.000", "artists": []}
                ]
                """,
                encoding="utf-8",
            )

    monkeypatch.setattr(module, "run_stage", fake_run_stage)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "full_pipeline.py",
            "--min-date",
            "2026-06-23",
            "--max-date",
            "2026-06-23",
            "--events-json",
            str(events_json),
            "--skip-bio",
            "--skip-tags",
            "--skip-embeddings",
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    assert seen_stages == ["scrape-and-parse"]
    assert events_json.with_name("import.json").read_text(encoding="utf-8") == "[]"
    assert events_json.with_name("event_ids.txt").read_text(encoding="utf-8") == ""
    assert events_json.with_name("artist_ids.txt").read_text(encoding="utf-8") == ""


def test_full_pipeline_backfills_existing_scope_when_dedup_leaves_no_new_events(monkeypatch, tmp_path):
    install_import_stubs()
    module = load_module(
        "scenegraph_full_pipeline_existing_scope",
        REPO_ROOT / "backend" / "scripts" / "full_pipeline.py",
    )
    today = datetime.now().strftime("%Y-%m-%d")
    events_json = tmp_path / "events.json"
    seen_stages: list[str] = []
    seen_commands: list[list[str]] = []

    monkeypatch.setattr(module, "ensure_writable_parent", lambda path: None)
    monkeypatch.setattr(module, "ensure_db_ready", lambda: None)
    monkeypatch.setattr(module, "ensure_playwright_available", lambda: None)
    monkeypatch.setattr(module, "ensure_cdp_ready", lambda cdp_url: None)
    monkeypatch.setattr(module, "ensure_provider_env", lambda skip_tags, skip_embeddings: None)
    monkeypatch.setattr(
        module,
        "fetch_existing_scope_ids",
        lambda database_url, min_date, max_date: ([2454507], [2178]),
    )

    def fake_run_stage(name, command, cwd=None, env=None):
        seen_stages.append(name)
        seen_commands.append(command)
        if name == "scrape-and-parse":
            events_json.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(module, "run_stage", fake_run_stage)
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
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    assert seen_stages == [
        "scrape-and-parse",
        "backfill-normalized-texts",
        "extract-event-tags",
        "extract-artist-tags",
        "generate-embeddings",
        "backfill-embedding-vectors",
        "validate-import",
    ]
    event_tag_cmd = next(command for command in seen_commands if "extract_event_tags.py" in " ".join(map(str, command)))
    assert "--continue-on-error" in event_tag_cmd
    assert events_json.with_name("event_ids.txt").read_text(encoding="utf-8").splitlines() == ["2454507"]
    assert events_json.with_name("artist_ids.txt").read_text(encoding="utf-8").splitlines() == ["2178"]


def test_full_pipeline_imports_biographies_for_existing_scope_without_new_events(monkeypatch, tmp_path):
    install_import_stubs()
    module = load_module(
        "scenegraph_full_pipeline_existing_bio_scope",
        REPO_ROOT / "backend" / "scripts" / "full_pipeline.py",
    )
    today = datetime.now().strftime("%Y-%m-%d")
    events_json = tmp_path / "events.json"
    bio_json = tmp_path / "artist_biographies.json"
    seen_stages: list[str] = []
    seen_commands: list[list[str]] = []

    monkeypatch.setattr(module, "ensure_writable_parent", lambda path: None)
    monkeypatch.setattr(module, "ensure_db_ready", lambda: None)
    monkeypatch.setattr(module, "ensure_playwright_available", lambda: None)
    monkeypatch.setattr(module, "ensure_cdp_ready", lambda cdp_url: None)
    monkeypatch.setattr(module, "ensure_provider_env", lambda skip_tags, skip_embeddings: None)
    monkeypatch.setattr(
        module,
        "fetch_existing_scope_ids",
        lambda database_url, min_date, max_date: ([2454507], [2178]),
    )

    def fake_run_stage(name, command, cwd=None, env=None):
        seen_stages.append(name)
        seen_commands.append(command)
        if name == "scrape-and-parse":
            events_json.write_text("[]", encoding="utf-8")
            bio_json.write_text(
                '[{"id":"2178","biography":"Fresh bio","status":"ok"}]',
                encoding="utf-8",
            )

    monkeypatch.setattr(module, "run_stage", fake_run_stage)
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
            "--bio-json",
            str(bio_json),
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
    import_cmd = next(command for command in seen_commands if "import_events.py" in " ".join(map(str, command)))
    assert "--biographies-path" in import_cmd
    assert str(bio_json) in import_cmd
    assert events_json.with_name("event_ids.txt").read_text(encoding="utf-8").splitlines() == ["2454507"]
    assert events_json.with_name("artist_ids.txt").read_text(encoding="utf-8").splitlines() == ["2178"]

def test_run_stage_records_success_and_failure(monkeypatch):
    install_import_stubs()
    module = load_module(
        "scenegraph_full_pipeline_stage_log",
        REPO_ROOT / "backend" / "scripts" / "full_pipeline.py",
    )
    finished: list[tuple[int | None, str, object | None]] = []

    class FakeImportLogger:
        def start_stage(self, name, command):
            return 7, 1.0

        def finish_stage(self, stage_id, status, started_at, error=None):
            finished.append((stage_id, status, error))

    monkeypatch.setattr(module, "ACTIVE_IMPORT_LOGGER", FakeImportLogger())
    monkeypatch.setattr(module, "print_stage", lambda name, command: None)

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: types.SimpleNamespace(returncode=0))
    module.run_stage("ok-stage", ["true"])

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: types.SimpleNamespace(returncode=2))
    try:
        module.run_stage("bad-stage", ["false"])
    except SystemExit as exc:
        assert "bad-stage failed with exit code 2" in str(exc)
    else:
        raise AssertionError("run_stage should exit when a stage command fails")

    assert finished == [
        (7, "succeeded", None),
        (7, "failed", "bad-stage failed with exit code 2"),
    ]
