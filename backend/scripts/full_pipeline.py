from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import date as date_class, datetime
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.artist_tag_extraction import TagExtractionConfig
from app.embeddings import EmbeddingConfig
from app.event_tag_extraction import EventTagExtractionConfig
from app.import_run_logger import ImportRunLogger
from app.schema_preflight import check_schema_tables, schema_preflight_strict_mode


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTISTS_JSON = REPO_ROOT / "backend" / "data" / "artists.json"
DEFAULT_BIO_JSON = REPO_ROOT / "backend" / "data" / "artist_biographies.json"
DEFAULT_IMPORT_RUNS_DIR = Path(
    os.environ.get(
        "FULL_PIPELINE_ARTIFACTS_DIR",
        str(REPO_ROOT / "backend" / "data" / "import_runs"),
    )
).expanduser()
DEFAULT_CDP_URL = os.environ.get("SCENEGRAPH_CDP_URL", "http://127.0.0.1:9222")
DEFAULT_MIN_DATE = "2021-01-01"
DEFAULT_MAX_DATE = ""
ACTIVE_IMPORT_LOGGER = ImportRunLogger.disabled()


def parse_iso_date(value: str) -> tuple[int, int, int]:
    year, month, day = value.split("-", 2)
    return int(year), int(month), int(day)


def event_in_date_range(event: dict[str, object], min_date: str, max_date: str) -> bool:
    raw_date = str(event.get("date") or "").strip()
    if not raw_date:
        return False

    candidate = raw_date[:10]
    if len(candidate) != 10:
        return False

    try:
        event_date = parse_iso_date(candidate)
    except ValueError:
        return False

    min_bound = parse_iso_date(min_date)
    max_bound = parse_iso_date(max_date)
    return min_bound <= event_date <= max_bound


def write_id_file(path: Path, ids: list[int]) -> None:
    unique_ids = sorted(dict.fromkeys(ids))
    path.write_text("\n".join(str(item) for item in unique_ids) + ("\n" if unique_ids else ""), encoding="utf-8")


def extract_event_ids(events: list[dict[str, object]]) -> list[int]:
    ids: list[int] = []
    for event in events:
        raw = event.get("id")
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    return ids


def extract_artist_ids(events: list[dict[str, object]]) -> list[int]:
    ids: list[int] = []
    for event in events:
        artists = event.get("artists", [])
        if not isinstance(artists, list):
            continue
        for artist in artists:
            if not isinstance(artist, dict):
                continue
            raw = artist.get("id")
            try:
                ids.append(int(raw))
            except (TypeError, ValueError):
                continue
    return ids


def safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value).strip("_")


def build_run_artifacts(
    *,
    artifacts_dir: Path,
    min_date: str,
    max_date: str,
) -> tuple[Path, Path, Path, Path]:
    date_slug = f"{safe_path_part(min_date)}_to_{safe_path_part(max_date)}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = artifacts_dir.expanduser().resolve() / f"{date_slug}_{timestamp}"
    return (
        run_dir / "events.json",
        run_dir / "artists.json",
        run_dir / "artist_biographies.json",
        run_dir,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full Scenegraph ingestion pipeline in Docker.")
    parser.add_argument("--min-date", default=DEFAULT_MIN_DATE, help="Oldest event date to crawl (YYYY-MM-DD).")
    parser.add_argument(
        "--max-date",
        default=DEFAULT_MAX_DATE,
        help="Newest event date to crawl (YYYY-MM-DD). Defaults to today if omitted.",
    )
    parser.add_argument(
        "--cdp-url",
        default=DEFAULT_CDP_URL,
        help="Chrome remote-debugging endpoint used by the biography scraper.",
    )
    parser.add_argument(
        "--events-json",
        type=Path,
        default=None,
        help=(
            "Path to the scraped events JSON artifact. If omitted, full-pipeline creates "
            "a fresh backend/data/import_runs/<date-range>_<timestamp>/ artifact directory."
        ),
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=DEFAULT_IMPORT_RUNS_DIR,
        help="Directory for per-run artifacts when --events-json is omitted.",
    )
    parser.add_argument(
        "--artists-json",
        type=Path,
        default=DEFAULT_ARTISTS_JSON,
        help="Path to the scraped artists JSON artifact.",
    )
    parser.add_argument(
        "--bio-json",
        type=Path,
        default=DEFAULT_BIO_JSON,
        help="Path to the artists biography JSON artifact.",
    )
    parser.add_argument(
        "--parse-python",
        type=Path,
        default=Path(sys.executable),
        help="Python executable for parse_past_events.py and artists_bio.py.",
    )
    parser.add_argument(
        "--no-launch-chrome",
        dest="launch_chrome",
        action="store_false",
        default=True,
        help="Do not auto-launch a local Chromium CDP endpoint when one is unavailable.",
    )
    parser.add_argument(
        "--chrome-binary",
        type=Path,
        default=Path("/app/tools/launch_chromium_cdp.sh"),
        help="Launcher script used to start a local Chromium CDP endpoint.",
    )
    parser.add_argument(
        "--chrome-startup-timeout",
        type=float,
        default=20.0,
        help="Seconds to wait for the local Chromium CDP endpoint after launch.",
    )
    parser.add_argument(
        "--no-dedup-with-db",
        dest="dedup_with_db",
        action="store_false",
        default=True,
        help="Disable DB-backed deduplication in the scraper stage.",
    )
    parser.add_argument(
        "--skip-bio",
        action="store_true",
        help="Skip the artists biography scraping stage.",
    )
    parser.add_argument(
        "--skip-tags",
        action="store_true",
        help="Skip event and artist tag extraction.",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip embedding generation.",
    )
    parser.add_argument(
        "--validate-artist-id",
        type=int,
        default=None,
        help="Optional artist id that must have at least one embedding row during validation.",
    )
    return parser.parse_args()


def print_stage(name: str, command: list[str]) -> None:
    print(f"\n==> {name}")
    print(shlex.join(command))


def run_stage(name: str, command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print_stage(name, command)
    stage_id, started_at = ACTIVE_IMPORT_LOGGER.start_stage(name, command)
    completed = subprocess.run(command, cwd=str(cwd or REPO_ROOT), env=env)
    if completed.returncode != 0:
        error = f"{name} failed with exit code {completed.returncode}"
        ACTIVE_IMPORT_LOGGER.finish_stage(stage_id, status="failed", started_at=started_at, error=error)
        raise SystemExit(error)
    ACTIVE_IMPORT_LOGGER.finish_stage(stage_id, status="succeeded", started_at=started_at)


def ensure_writable_parent(path: Path) -> None:
    parent = path if path.suffix == "" else path.parent
    parent.mkdir(parents=True, exist_ok=True)
    test_file = parent / ".write-test"
    try:
        test_file.write_text("ok", encoding="utf-8")
    finally:
        test_file.unlink(missing_ok=True)


def ensure_cdp_ready(cdp_url: str) -> None:
    parsed = urlparse(cdp_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit(f"Invalid CDP URL: {cdp_url}")
    version_url = cdp_url.rstrip("/") + "/json/version"
    try:
        with urllib.request.urlopen(version_url, timeout=3) as response:
            if response.status != 200:
                raise SystemExit(f"Chrome CDP is not ready at {version_url} (HTTP {response.status})")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"Chrome CDP is not ready at {version_url}: {exc}") from exc


def is_local_cdp_url(cdp_url: str) -> bool:
    parsed = urlparse(cdp_url)
    return (parsed.hostname or "").lower() in {"localhost", "127.0.0.1", "::1"}


def ensure_playwright_available() -> None:
    try:
        import playwright.async_api  # noqa: F401
    except Exception as exc:  # pragma: no cover - import guard
        raise SystemExit(f"Playwright is required for the biography scraper: {exc}") from exc


def launch_local_chrome(args: argparse.Namespace) -> subprocess.Popen[bytes]:
    if not args.chrome_binary.exists():
        raise SystemExit(f"Chrome launcher not found: {args.chrome_binary}")

    env = os.environ.copy()
    env["CDP_PORT"] = str(urlparse(args.cdp_url).port or 9222)
    env.setdefault("CHROME_START_URL", "about:blank")
    env.setdefault("CHROME_USER_DATA_DIR", "/tmp/scenegraph-browser-profile")

    print(f"Launching local Chromium CDP via {args.chrome_binary}")
    return subprocess.Popen([str(args.chrome_binary)], cwd=str(REPO_ROOT), env=env)


def ensure_provider_env(skip_tags: bool, skip_embeddings: bool) -> None:
    if not skip_tags:
        event_config = EventTagExtractionConfig.from_env()
        artist_config = TagExtractionConfig.from_env()
        if event_config.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY must be set for event tag extraction")
        if artist_config.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY must be set for artist tag extraction")
        if event_config.provider == "azure":
            if not os.environ.get("AZURE_OPENAI_API_KEY"):
                raise SystemExit("AZURE_OPENAI_API_KEY must be set for event tag extraction")
            if event_config.api == "responses":
                if not event_config.azure_responses_url:
                    raise SystemExit("AZURE_OPENAI_RESPONSES_URL must be set for Azure event tag extraction")
            elif not os.environ.get("AZURE_OPENAI_ENDPOINT"):
                raise SystemExit("AZURE_OPENAI_ENDPOINT must be set for Azure event tag extraction")
        if artist_config.provider == "azure":
            if not os.environ.get("AZURE_OPENAI_API_KEY"):
                raise SystemExit("AZURE_OPENAI_API_KEY must be set for artist tag extraction")
            if artist_config.api == "responses":
                if not artist_config.azure_responses_url:
                    raise SystemExit("AZURE_OPENAI_RESPONSES_URL must be set for Azure artist tag extraction")
            elif not os.environ.get("AZURE_OPENAI_ENDPOINT"):
                raise SystemExit("AZURE_OPENAI_ENDPOINT must be set for artist tag extraction")

    if not skip_embeddings:
        embedding_config = EmbeddingConfig.from_env()
        if embedding_config.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY must be set for embeddings")
        if embedding_config.provider == "azure":
            if not os.environ.get("AZURE_OPENAI_API_KEY"):
                raise SystemExit("AZURE_OPENAI_API_KEY must be set for Azure embeddings")
            if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
                raise SystemExit("AZURE_OPENAI_ENDPOINT must be set for Azure embeddings")


def ensure_db_ready() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL must be set")

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        schema_status = check_schema_tables(connection)
        if schema_status["status"] == "error" and schema_preflight_strict_mode():
            missing = ", ".join(schema_status["missingRequiredTables"])
            raise SystemExit(f"Database schema is missing required tables: {missing}")


def main() -> int:
    global ACTIVE_IMPORT_LOGGER
    args = parse_args()

    if not args.parse_python.exists():
        raise SystemExit(f"parse-python executable not found: {args.parse_python}")

    min_date = args.min_date or DEFAULT_MIN_DATE
    max_date = args.max_date or date_class.today().isoformat()

    if args.events_json is None:
        events_json, artists_json, bio_json, run_artifacts_dir = build_run_artifacts(
            artifacts_dir=args.artifacts_dir,
            min_date=min_date,
            max_date=max_date,
        )
    else:
        events_json = args.events_json.expanduser().resolve()
        artists_json = args.artists_json.expanduser().resolve()
        bio_json = args.bio_json.expanduser().resolve()
        run_artifacts_dir = events_json.parent

    ensure_writable_parent(events_json)
    ensure_writable_parent(artists_json)
    ensure_writable_parent(bio_json)
    run_artifacts_dir.mkdir(parents=True, exist_ok=True)
    ensure_db_ready()
    chrome_proc: subprocess.Popen[bytes] | None = None
    if not args.skip_bio:
        ensure_playwright_available()
        try:
            ensure_cdp_ready(args.cdp_url)
        except SystemExit:
            if not args.launch_chrome or not is_local_cdp_url(args.cdp_url):
                raise
            chrome_proc = launch_local_chrome(args)
            deadline = time.time() + max(1.0, args.chrome_startup_timeout)
            while True:
                try:
                    ensure_cdp_ready(args.cdp_url)
                    break
                except SystemExit:
                    if chrome_proc.poll() is not None:
                        raise
                    if time.time() >= deadline:
                        raise
                    time.sleep(1.0)
    ensure_provider_env(args.skip_tags, args.skip_embeddings)

    event_ids_file = run_artifacts_dir / "event_ids.txt"
    artist_ids_file = run_artifacts_dir / "artist_ids.txt"
    ACTIVE_IMPORT_LOGGER = ImportRunLogger.start(
        min_date=min_date,
        max_date=max_date,
        events_json=events_json,
        event_ids_file=event_ids_file,
        artist_ids_file=artist_ids_file,
        metadata={
            "skipBio": args.skip_bio,
            "skipTags": args.skip_tags,
            "skipEmbeddings": args.skip_embeddings,
            "dedupWithDb": args.dedup_with_db,
            "cdpUrl": args.cdp_url,
        },
    )

    try:
        parse_cmd = [
            str(args.parse_python),
            str(REPO_ROOT / "parsers" / "run_ra_pipeline.py"),
            "--parse-python",
            str(args.parse_python),
            "--events-json",
            str(events_json),
            "--artists-json",
            str(artists_json),
            "--bio-json",
            str(bio_json),
            "--cdp-url",
            args.cdp_url,
            "--events-min-date",
            min_date,
            "--events-max-date",
            max_date,
        ]
        if args.dedup_with_db:
            parse_cmd.append("--dedup-with-db")
        else:
            parse_cmd.append("--no-dedup-with-db")
        if args.skip_bio:
            parse_cmd.append("--skip-bio")

        run_stage("scrape-and-parse", parse_cmd)

        events_payload = json.loads(events_json.read_text(encoding="utf-8"))
        if not isinstance(events_payload, list):
            raise SystemExit(f"Expected a JSON list in {events_json}")

        import_events_json = events_json
        if args.min_date or args.max_date:
            import_events_json = run_artifacts_dir / "import.json"
            filtered_events = [
                event
                for event in events_payload
                if isinstance(event, dict) and event_in_date_range(event, min_date, max_date)
            ]
            import_events_json.write_text(json.dumps(filtered_events, ensure_ascii=False, indent=2), encoding="utf-8")
            event_ids = extract_event_ids(filtered_events)
            artist_ids = extract_artist_ids(filtered_events)
            write_id_file(event_ids_file, event_ids)
            write_id_file(artist_ids_file, artist_ids)
            print(f"[pipeline] Filtered {len(filtered_events)} events for import into {import_events_json}")
        else:
            event_ids = extract_event_ids(events_payload)
            artist_ids = extract_artist_ids(events_payload)
            write_id_file(event_ids_file, event_ids)
            write_id_file(artist_ids_file, artist_ids)

        ACTIVE_IMPORT_LOGGER.update(
            import_json=import_events_json,
            metrics={
                "event_count": len(set(event_ids)),
                "artist_count": len(set(artist_ids)),
            },
        )

        if not event_ids:
            print("[pipeline] No events matched the requested date range after dedup/filtering; nothing to import.")
            ACTIVE_IMPORT_LOGGER.update(status="succeeded")
            print("\nFull pipeline completed successfully.")
            return 0

        import_cmd = [
            str(args.parse_python),
            str(REPO_ROOT / "backend" / "scripts" / "import_events.py"),
            str(import_events_json),
        ]
        if not args.skip_bio:
            import_cmd.extend(["--biographies-path", str(bio_json)])
        run_stage("import-to-db", import_cmd)

        run_stage(
            "backfill-normalized-texts",
            [
                str(args.parse_python),
                str(REPO_ROOT / "backend" / "scripts" / "backfill_normalized_texts.py"),
                "--event-ids-file",
                str(event_ids_file),
                "--artist-ids-file",
                str(artist_ids_file),
            ],
        )

        if not args.skip_tags:
            run_stage(
                "extract-event-tags",
                [
                    str(args.parse_python),
                    str(REPO_ROOT / "backend" / "scripts" / "extract_event_tags.py"),
                    "--event-ids-file",
                    str(event_ids_file),
                ],
            )
            run_stage(
                "extract-artist-tags",
                [
                    str(args.parse_python),
                    str(REPO_ROOT / "backend" / "scripts" / "extract_artist_tags.py"),
                    "--artist-ids-file",
                    str(artist_ids_file),
                ],
            )

        if not args.skip_embeddings:
            run_stage(
                "generate-embeddings",
                [
                    str(args.parse_python),
                    str(REPO_ROOT / "backend" / "scripts" / "generate_embeddings.py"),
                    "--event-ids-file",
                    str(event_ids_file),
                    "--artist-ids-file",
                    str(artist_ids_file),
                ],
            )
            run_stage(
                "backfill-embedding-vectors",
                [
                    str(args.parse_python),
                    str(REPO_ROOT / "backend" / "scripts" / "backfill_embedding_vectors.py"),
                    "--event-ids-file",
                    str(event_ids_file),
                    "--artist-ids-file",
                    str(artist_ids_file),
                ],
            )

        validate_cmd = [
            str(args.parse_python),
            str(REPO_ROOT / "backend" / "scripts" / "validate_import.py"),
            "--event-ids-file",
            str(event_ids_file),
            "--artist-ids-file",
            str(artist_ids_file),
        ]
        if not args.skip_embeddings:
            validate_cmd.append("--require-embeddings")
        if args.validate_artist_id is not None:
            validate_cmd.extend(["--check-artist-id", str(args.validate_artist_id)])
        if not args.skip_bio:
            validate_cmd.extend(["--biographies-path", str(bio_json)])
        run_stage("validate-import", validate_cmd)

        final_metrics = ACTIVE_IMPORT_LOGGER.collect_metrics(event_ids, artist_ids) if ACTIVE_IMPORT_LOGGER.enabled else {}
        ACTIVE_IMPORT_LOGGER.update(status="succeeded", metrics=final_metrics)
        print("\nFull pipeline completed successfully.")
        return 0
    except BaseException as exc:
        ACTIVE_IMPORT_LOGGER.update(status="failed", error=exc)
        raise
    finally:
        ACTIVE_IMPORT_LOGGER = ImportRunLogger.disabled()
        if chrome_proc is not None and chrome_proc.poll() is None:
            chrome_proc.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
